class Telescope:
    """Simple data model for telescope settings."""

    def __init__(self, name, slew_speed, dwell_time):
        self.name = name
        self.slew_speed = slew_speed
        self.dwell_time = dwell_time

