"""Presentation dimensions are ratios of the container, not railway metres."""

from pydantic import BaseModel, ConfigDict, Field


class KeyPlanOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    width: float = Field(default=420, ge=210, le=1680)
    height: float = Field(default=150, ge=100, le=1200)
    left_destination: str = Field(default="", max_length=100)
    right_destination: str = Field(default="", max_length=100)
    station_caption: str = Field(default="", max_length=160)
    # Degrees counterclockwise from the key plan's positive X direction.
    # None retains the survey orientation captured during KML conversion.
    north_angle: float | None = Field(default=None, ge=-360, le=360)

    @property
    def font(self):
        return self.height * 0.014

    @property
    def track_bottom(self):
        return self.height * 0.30

    @property
    def track_height(self):
        return self.height * 0.40

    @property
    def padding_x(self):
        return self.width * (50 / 420)
