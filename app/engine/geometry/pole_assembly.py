"""Geometry and ordering of assembled pole segments.

Ported from python_calc ``calculation/pole_assembly.py``.
DEVIATION: rounding follows VBA (see app/engine/rounding.py).
"""

from collections.abc import Iterable

from app.engine import rounding
from app.engine.results import PoleActiveGeometry
from app.engine.loads.pole import PoleObject


class PoleAssembly:
    """Arrange pole segments and evaluate their active geometry.

    ``top_elevation_m`` identifies the top of each segment. The bottom of the
    lowest segment is ``base_elevation_m``; every following segment starts at
    the top elevation of the segment below it.
    """

    def __init__(
        self,
        poles: Iterable[PoleObject],
        base_elevation_m: float = 0.0,
    ) -> None:
        self.base_elevation_m = float(base_elevation_m)
        self.poles = tuple(sorted(poles, key=lambda pole: pole.top_elevation_m))
        self._validate()

    def _validate(self) -> None:
        if not self.poles:
            raise ValueError("PoleAssembly requires at least one pole segment")
        if any(not isinstance(pole, PoleObject) for pole in self.poles):
            raise TypeError("PoleAssembly accepts only PoleObject instances")

        elevations = [pole.top_elevation_m for pole in self.poles]
        if elevations[0] <= self.base_elevation_m:
            raise ValueError("First pole top must be above the base elevation")
        if len(elevations) != len(set(elevations)):
            raise ValueError("Pole top elevations must be unique")

    def segment_bounds(self, pole: PoleObject) -> tuple[float, float]:
        """Return the physical bottom and top elevation of a pole segment."""
        try:
            index = self.poles.index(pole)
        except ValueError:
            raise ValueError(f"Pole {pole.name!r} is not part of this assembly") from None

        bottom = (
            self.base_elevation_m
            if index == 0
            else self.poles[index - 1].top_elevation_m
        )
        return bottom, pole.top_elevation_m

    def active_poles(self, evaluated_position_m: float) -> tuple[PoleObject, ...]:
        """Return pole segments having material above the evaluated position."""
        return tuple(
            pole
            for pole in self.poles
            if pole.top_elevation_m > evaluated_position_m
        )

    def active_geometry(
        self,
        pole: PoleObject,
        evaluated_position_m: float,
    ) -> PoleActiveGeometry:
        """Return active pole geometry above one evaluated position."""
        segment_bottom, segment_top = self.segment_bounds(pole)
        full_length = segment_top - segment_bottom
        active_bottom = min(
            max(segment_bottom, float(evaluated_position_m)),
            segment_top,
        )
        active_top = segment_top
        active_length = max(0.0, active_top - active_bottom)

        if active_length == 0:
            diameter_bottom = pole.diameter_upper_mm
            diameter_top = pole.diameter_upper_mm
            local_center = 0.0
            load_center_height = 0.0
        else:
            bottom_distance_from_top = segment_top - active_bottom
            top_distance_from_top = segment_top - active_top
            diameter_bottom = pole.diameter_at(
                bottom_distance_from_top,
                full_length,
            )
            
            if pole.is_tapered:
                diameter_bottom = rounding.TAPER_DIAMETER(diameter_bottom)
                
            diameter_top = pole.diameter_at(
                top_distance_from_top,
                full_length,
            )
            local_center = pole.local_load_center(
                active_length,
                diameter_bottom,
                diameter_top,
            )
            load_center_height = rounding.SIG3(
                active_bottom - evaluated_position_m + local_center
            )

        return PoleActiveGeometry(
            pole_name=pole.name,
            evaluated_position_m=float(evaluated_position_m),
            segment_bottom_m=segment_bottom,
            segment_top_m=segment_top,
            active_bottom_m=active_bottom,
            active_top_m=active_top,
            full_length_m=full_length,
            active_length_m=active_length,
            diameter_at_active_bottom_mm=diameter_bottom,
            diameter_at_active_top_mm=diameter_top,
            local_load_center_m=local_center,
            load_center_height_m=load_center_height,
        )

    def geometries_at(
        self,
        evaluated_position_m: float,
    ) -> tuple[PoleActiveGeometry, ...]:
        """Return active geometry for all pole segments, ordered bottom-up."""
        return tuple(
            self.active_geometry(pole, evaluated_position_m)
            for pole in self.active_poles(evaluated_position_m)
        )

