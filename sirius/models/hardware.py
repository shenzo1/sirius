import datetime

from sirius.coding import bitshuffle

from sirius.models.db import db


class Bridge(db.Model):
    """Bridges are not really interesting for users other than that they
    are connected so we don't store ownership for them.
    """
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    bridge_address = db.Column(db.String, primary_key=True)


class Printer(db.Model):
    """On reset printers generate a new, unique device address, so every
    reset will result in a new Printer row.

    Note that this model is only ever created by a printer calling
    home. Users create a ClaimCode row.
    """
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    device_address = db.Column(db.String)
    hardware_xor = db.Column(db.Integer)

    # Update the following fields after we connected (i.e. joined over
    # hardware xor) a claim to a printer. The fields start out as
    # NULL.
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    owner = db.relationship('User', backref=db.backref('printers', lazy='dynamic'))

    used_claim_code = db.Column(db.String, nullable=True)

    def __repr__(self):
        return 'Printer {}, xor: {}, owner: {}'.format(
            self.device_address, self.hardware_xor, self.owner_id)

    @classmethod
    def phone_home(cls, device_address):
        """This gets called every time the in-memory machinery thinks it has
        seen a printer for the first time round, e.g. after a
        re-connect of the websocket.
        """
        printer = cls.query.filter_by(device_address=device_address).first()
        hardware_xor = bitshuffle.hardware_xor_from_device_address(device_address)

        if printer is not None:
            return

        printer = cls(
            device_address=device_address,
            hardware_xor=hardware_xor,
            owner_id=None,
            used_claim_code=None,
        )
        db.session.add(printer)

        # Connect hardware xor and printer if there is a claim code
        # waiting.
        claim_code_query = ClaimCode.query.filter_by(hardware_xor=hardware_xor)
        claim_code = claim_code_query.first()
        if claim_code is None:
            return

        assert claim_code_query.count() == 1, \
            "claim code hardware xor collision: {}".format(hardware_xor)

        printer.owner_id = claim_code.by_id
        printer.used_claim_code = claim_code.claim_code
        db.session.add(printer)


class ClaimCode(db.Model):
    """Printer and claim codes are joined over the hardware xor. Claim
    codes are meant to have a temporary life time though we're not
    treating them like this for now.
    """
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    by_id = db.Column(db.ForeignKey('user.id'))
    hardware_xor = db.Column(db.Integer)
    claim_code = db.Column(db.String)

    def __repr__(self):
        return '<ClaimCode xor: {} code: {}>'.format(self.hardware_xor, self.claim_code)


class DeviceLog(db.Model):
    """The device log Recorde state changes in the bridge and connected
    devices. We may selectively expose some of these to the user.
    """
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    device_address = db.Column(db.String)

    # json dict of events dispatched on VALID_STATES. E.g.
    # {"type": "grant_access", "payload": {...}}
    entry = db.Column(db.String)

    VALID_STATES = [
        'power_on',
        'connect',
        'disconnect',
        'claim',
        'print',
        'grant_access',
        'revoke_access',
    ]

    # Expose an explicit API to force people to provide the correct
    # arguments.
    @classmethod
    def log_power_on(cls, bridge_address):
        pass

    @classmethod
    def log_connect(cls, device_address):
        pass

    @classmethod
    def log_disconnect(cls, device_address):
        pass

    # TODO log all the things
