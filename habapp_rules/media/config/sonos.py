import HABApp.openhab.items.thing_item
import pydantic
from typing_extensions import Self

import habapp_rules.core.pydantic_base


class _KnownContentBase(pydantic.BaseModel):
    """Base class for known content."""

    display_text: str = pydantic.Field(..., description="display string for known content", max_length=14)
    favorite_id: int | None = pydantic.Field(None, description="favorite id for known content", gt=0)  # fav id 0 is reserved for OFF
    start_volume: int | None = pydantic.Field(None, description="start volume. None means no volume")


class ContentTuneIn(_KnownContentBase):
    """TuneIn Radio content."""

    tune_in_id: int = pydantic.Field(..., description="TuneIn id for radio content")


class ContentPlayUri(_KnownContentBase):
    """PlayUri content."""

    uri: str = pydantic.Field(..., description="uri for play uri content")


class SonosItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for sonos."""

    sonos_thing: HABApp.openhab.items.Thing = pydantic.Field(..., description="sonos thing")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="sonos state")
    power_switch: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="sonos power switch")
    sonos_player: HABApp.openhab.items.PlayerItem = pydantic.Field(..., description="sonos controller")
    current_track_uri: HABApp.openhab.items.StringItem = pydantic.Field(..., description="sonos current track uri item")
    sonos_volume: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="sonos volume")
    play_uri: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sonos play uri item")
    tune_in_station_id: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sonos tune in station id item")
    favorite_id: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="favorite id item")
    display_string: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="display string item")
    presence_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="presence state item")


class SonosParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for sonos."""

    known_content: list[ContentTuneIn | ContentPlayUri] = pydantic.Field(default_factory=list, description="known content")
    lock_time_volume: int | None = pydantic.Field(None, description="lock time for automatic volume setting in seconds after manual volume change. None means no lock")
    start_volume_tune_in: int | None = pydantic.Field(None, description="start volume for tune in. None means no volume")
    start_volume_line_in: int | None = pydantic.Field(None, description="start volume for line in. None means no volume")
    start_volume_unknown: int | None = pydantic.Field(None, description="start volume for unknown content. None means no volume")
    booting_timeout: int = pydantic.Field(300, description="timeout for booting sonos devices. After this timeout the state will fallback to PowerOff if the device did not come online.", gt=0)
    starting_timeout: int = pydantic.Field(60, description="timeout for starting new content in seconds. After this timeout the state will fallback to standby if no content is playing", gt=0)
    favorite_id_unknown_content: int = pydantic.Field(-1, description="Favorite ID which is set if unknown content is playing. Default is -1, but can be set to another value e.g. to set correct LED state on a KNX device")

    @pydantic.field_validator("known_content", mode="after")
    @classmethod
    def validate_known_content(cls, value: list[ContentTuneIn | ContentPlayUri]) -> list[ContentTuneIn | ContentPlayUri]:
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

    def check_if_known_tune_in(self, tune_in_id: int) -> ContentTuneIn | None:
        """Check if tune in id is known.

        Args:
            tune_in_id: tune in id

        Returns:
            instance of ContentTuneIn (or None if not found)
        """
        return next((content for content in self.known_content if isinstance(content, ContentTuneIn) and content.tune_in_id == tune_in_id), None)

    def check_if_known_play_uri(self, uri: str) -> ContentPlayUri | None:
        """Check if play uri is known.

        Args:
            uri: play uri

        Returns:
            instance of ContentPlayUri (or None if not found)
        """
        return next((content for content in self.known_content if isinstance(content, ContentPlayUri) and content.uri == uri), None)

    def get_known_content_by_favorite_id(self, favorite_id: int) -> ContentTuneIn | ContentPlayUri | None:
        """Get known content instance by favorite ID.

        Args:
            favorite_id: favorite ID

        Returns:
            instance of ContentTuneIn or ContentPlayUri (or None if not found)
        """
        return next((content for content in self.known_content if content.favorite_id == favorite_id), None)


class SonosConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for sonos."""

    items: SonosItems = pydantic.Field(..., description="sonos items")
    parameter: SonosParameter = pydantic.Field(..., description="sonos parameter")

    @pydantic.model_validator(mode="after")
    def _validate_model(self) -> Self:
        """Validate model.

        Returns:
            validated model

        Raises:
            ValueError: if validation fails
        """
        if any(isinstance(content, ContentTuneIn) for content in self.parameter.known_content) and self.items.tune_in_station_id is None:
            msg = "tune_in_station_id item must be set if ContentTuneIn is used"
            raise ValueError(msg)

        if any(isinstance(content, ContentPlayUri) for content in self.parameter.known_content) and self.items.play_uri is None:
            msg = "play_uri item must be set if ContentPlayUri is used"
            raise ValueError(msg)

        start_volumes = [self.parameter.start_volume_tune_in, self.parameter.start_volume_line_in, self.parameter.start_volume_unknown] + [content.start_volume for content in self.parameter.known_content]
        if any(volume is not None for volume in start_volumes) and self.items.sonos_volume is None:
            msg = "sonos_volume item must be set if start volume is configured"
            raise ValueError(msg)

        if self.parameter.lock_time_volume is not None and self.items.sonos_volume is None:
            msg = "sonos_volume item must be set if lock time volume is configured"
            raise ValueError(msg)

        return self
