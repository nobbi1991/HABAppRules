import typing

import HABApp.openhab.items.thing_item
import pydantic

import habapp_rules.core.pydantic_base


class KnownContentBase(pydantic.BaseModel):
    """Base class for known content."""

    display_text: str = pydantic.Field(..., description="display string for known content")
    favorite_id: int | None = pydantic.Field(None, description="favorite id for known content", gt=0)  # fav id 0 is reserved for OFF
    start_volume: int | None = pydantic.Field(None, description="start volume. None means no volume")


class ContentTuneIn(KnownContentBase):
    """TuneIn Radio content."""

    tune_in_id: int = pydantic.Field(..., description="TuneIn id for radio content")


class ContentPlayUri(KnownContentBase):
    """PlayUri content."""

    uri: str = pydantic.Field(..., description="uri for play uri content")


class ContentLineIn(KnownContentBase):
    """LineIn content."""

    favorite_id: None = None


class SonosItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for sonos."""

    sonos_thing: HABApp.openhab.items.Thing = pydantic.Field(..., description="sonos thing")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="sonos state")
    power_switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="sonos power switch")
    sonos_player: HABApp.openhab.items.PlayerItem = pydantic.Field(..., description="sonos controller")
    sonos_volume: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="sonos volume")  # TODO add to unit test
    play_uri: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sonos play uri item")
    current_track_uri: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sonos current track uri item")
    tune_in_station_id: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sonos tune in station id item")
    line_in: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="sonos line in item")
    favorite_id: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="favorite id item")
    display_string: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="display string item")


class SonosParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for sonos."""

    known_content: list[KnownContentBase] = pydantic.Field(default_factory=list, description="known content")
    lock_time_volume: int | None = pydantic.Field(None, description="lock time for automatic volume setting in seconds after manual volume change. None means no lock")
    start_volume_tune_in: int | None = pydantic.Field(None, description="start volume for tune in. None means no volume")
    start_volume_line_in: int | None = pydantic.Field(None, description="start volume for line in. None means no volume")
    start_volume_unknown: int | None = pydantic.Field(None, description="start volume for unknown content. None means no volume")

    @pydantic.field_validator("known_content", mode="after")
    @classmethod
    def validate_known_content(cls, value: list[KnownContentBase]) -> list[KnownContentBase]:
        """Validate known content.

        Args:
            value: list of known content

        Returns:
            validated list of known content

        Raises:
            ValueError: if validation fails
        """
        favorite_ids = [content.favorite_id for content in value if content.favorite_id is not None]
        if len(set(favorite_ids)) != len(favorite_ids):
            msg = "favorite ids must be unique"
            raise ValueError(msg)
        return value

    def get_known_tune_in_ids(self) -> list[int]:
        """Get known tune in ids.

        Returns:
            list of known tune in ids
        """
        return [content.tune_in_id for content in self.known_content if isinstance(content, ContentTuneIn)]

    def get_known_play_uris(self) -> list[str]:
        """Get known play uris.

        Returns:
            list of known play uris
        """
        return [content.uri for content in self.known_content if isinstance(content, ContentPlayUri)]


class SonosConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for sonos."""

    items: SonosItems = pydantic.Field(..., description="sonos items")
    parameter: SonosParameter = pydantic.Field(..., description="sonos parameter")

    @pydantic.model_validator(mode="after")
    def _validate_model(self) -> typing.Self:
        """Validate model.

        Returns:
            validated model

        Raises:
            ValueError: if validation fails
        """
        if any(isinstance(content, ContentTuneIn) for content in self.parameter.known_content) and self.items.tune_in_station_id is None:
            msg = "tune_in_station_id item must be set if ContentTuneIn is used"
            raise ValueError(msg)

        if any(isinstance(content, ContentPlayUri) for content in self.parameter.known_content) and (self.items.play_uri is None or self.items.current_track_uri is None):
            msg = "play_uri and current_track_uri items must be set if ContentPlayUri is used"
            raise ValueError(msg)

        if any(isinstance(content, ContentLineIn) for content in self.parameter.known_content) and self.items.line_in is None:
            msg = "line_in item must be set if ContentLineIn is used"
            raise ValueError(msg)

        start_volumes = [self.parameter.start_volume_tune_in, self.parameter.start_volume_line_in, self.parameter.start_volume_unknown] + [content.start_volume for content in self.parameter.known_content]
        if any(volume is not None for volume in start_volumes) and self.items.sonos_volume is None:
            msg = "sonos_volume item must be set if start volume is configured"
            raise ValueError(msg)

        if self.parameter.lock_time_volume is not None and self.items.sonos_volume is None:
            msg = "sonos_volume item must be set if lock time volume is configured"
            raise ValueError(msg)

        return self
