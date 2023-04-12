"""
Flow360 solver parameters
"""
from __future__ import annotations
from typing import Dict, List, Optional, Union
from enum import Enum
import math
from abc import ABC
from typing_extensions import Literal
import pydantic as pd

from .types import (
    Axis,
    Coordinate,
    PositiveFloat,
    MomentLengthType,
    BoundaryVelocityType,
    PositiveInt,
    NonNegativeInt,
    Omega,
    Velocity,
    TimeStep,
)
from .params_base import Flow360BaseModel, Flow360SortableBaseModel, export_to_flow360
from .utils import beta_feature, _get_value_or_none
from .constants import constants
from ..exceptions import ValidationError, ConfigError, Flow360NotImplementedError


# pylint: disable=invalid-name
def get_time_non_dim_unit(mesh_unit_length, C_inf, extra_msg=""):
    """
    returns time non-dimensionalisation
    """

    if mesh_unit_length is None or C_inf is None:
        required = ["mesh_unit", "mesh_unit_length"]
        raise ConfigError(f"You need to provide one of {required} AND C_inf {extra_msg}")
    return mesh_unit_length / C_inf


def get_length_non_dim_unit(mesh_unit_length, extra_msg=""):
    """
    returns length non-dimensionalisation
    """
    if mesh_unit_length is None:
        required = ["mesh_unit", "mesh_unit_length"]
        raise ConfigError(f"You need to provide one of {required} {extra_msg}")
    return mesh_unit_length


class MeshBoundary(Flow360BaseModel):
    """Mesh boundary"""

    no_slip_walls: Union[List[str], List[int]] = pd.Field(alias="noSlipWalls")


class Boundary(ABC, Flow360BaseModel):
    """Basic Boundary class"""

    type: str
    name: Optional[str] = pd.Field(
        None, title="Name", description="Optional unique name for boundary."
    )


class NoSlipWall(Boundary):
    """No slip wall boundary"""

    type = pd.Field("NoSlipWall", const=True)
    velocity: Optional[BoundaryVelocityType] = pd.Field(alias="Velocity")


class SlipWall(Boundary):
    """Slip wall boundary"""

    type = pd.Field("SlipWall", const=True)


class FreestreamBoundary(Boundary):
    """Freestream boundary"""

    type = pd.Field("Freestream", const=True)
    velocity: Optional[BoundaryVelocityType] = pd.Field(alias="Velocity")


class IsothermalWall(Boundary):
    """IsothermalWall boundary"""

    type = pd.Field("IsothermalWall", const=True)
    Temperature: Union[PositiveFloat, str]
    velocity: Optional[BoundaryVelocityType] = pd.Field(alias="Velocity")


class SubsonicOutflowPressure(Boundary):
    """SubsonicOutflowPressure boundary"""

    type = pd.Field("SubsonicOutflowPressure", const=True)
    staticPressureRatio: PositiveFloat


class SubsonicOutflowMach(Boundary):
    """SubsonicOutflowMach boundary"""

    type = pd.Field("SubsonicOutflowMach", const=True)
    Mach: PositiveFloat = pd.Field(alias="MachNumber")


class SubsonicInflow(Boundary):
    """SubsonicInflow boundary"""

    type = pd.Field("SubsonicInflow", const=True)
    totalPressureRatio: PositiveFloat
    totalTemperatureRatio: PositiveFloat
    rampSteps: PositiveInt


class SlidingInterfaceBoundary(Boundary):
    """SlidingInterface boundary"""

    type = pd.Field("SlidingInterface", const=True)


class WallFunction(Boundary):
    """WallFunction boundary"""

    type = pd.Field("WallFunction", const=True)

    @beta_feature(type.default)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MassInflow(Boundary):
    """MassInflow boundary"""

    type = pd.Field("MassInflow", const=True)
    massFlowRate: PositiveFloat


class MassOutflow(Boundary):
    """MassOutflow boundary"""

    type = pd.Field("MassOutflow", const=True)
    massFlowRate: PositiveFloat


BoundaryType = Union[
    NoSlipWall,
    SlipWall,
    FreestreamBoundary,
    IsothermalWall,
    SubsonicOutflowPressure,
    SubsonicOutflowMach,
    SubsonicInflow,
    SlidingInterfaceBoundary,
    WallFunction,
    MassInflow,
    MassOutflow,
]


class ForcePerArea(Flow360BaseModel):
    """:class:`ForcePerArea` class for setting up force per area for Actuator Disk

    Parameters
    ----------
    radius : Coordinate
        Radius of the sampled locations in grid unit

    thrust : Axis
        Force per area in the axial direction, positive means the axial force follows the same direction as axisThrust.
        It is non-dimensional: trustPerArea[SI=N/m2]/rho_inf/C_inf^2

    circumferential : PositiveFloat
        Force per area in the circumferential direction, positive means the circumferential force follows the same
        direction as axisThrust with the right hand rule. It is non-dimensional:
                                                                circumferentialForcePerArea[SI=N/m2]/rho_inf/C_inf^2

    Returns
    -------
    :class:`ForcePerArea`
        An instance of the component class ForcePerArea.

    Example
    -------
    >>> fpa = ForcePerArea(radius=[0, 1], thrust=[1, 1], circumferential=[1, 1]) # doctest: +SKIP
    """

    radius: List[float]
    thrust: List[float]
    circumferential: List[float]

    # pylint: disable=no-self-argument
    @pd.root_validator(pre=True)
    def check_len(cls, values):
        """
        root validator
        """
        radius, thrust, circumferential = (
            values.get("radius"),
            values.get("thrust"),
            values.get("circumferential"),
        )
        if len(radius) != len(thrust) or len(radius) != len(circumferential):
            raise ValidationError(
                f"length of radius, thrust, circumferential must be the same, \
                but got: len(radius)={len(radius)}, \
                         len(thrust)={len(thrust)}, \
                         len(circumferential)={len(circumferential)}"
            )

        return values


class ActuatorDisk(Flow360BaseModel):
    """:class:`ActuatorDisk` class for setting up an Actuator Disk

    Parameters
    ----------
    center : Coordinate
        Coordinate of center of ActuatorDisk, eg (0, 0, 0)

    axis_thrust : Axis
        direction of thrust, it is a unit vector

    thickness : PositiveFloat
        Thickness of Actuator Disk in mesh units

    force_per_area : :class:`ForcePerArea`
        Force per Area data for actuator disk. See ActuatorDisk.ForcePerArea for details

    Returns
    -------
    :class:`ActuatorDisk`
        An instance of the component class ActuatorDisk.

    Example
    -------
    >>> ad = ActuatorDisk(center=(0, 0, 0), axis_thrust=(0, 0, 1), thickness=20,
    ... force_per_area=ForcePerArea(...))
    """

    center: Coordinate
    axis_thrust: Axis = pd.Field(alias="axisThrust")
    thickness: PositiveFloat
    force_per_area: ForcePerArea = pd.Field(alias="forcePerArea")


class SlidingInterface(Flow360BaseModel):
    """:class:`SlidingInterface` class for setting up sliding interface

    Parameters
    ----------
    center : Coordinate
        Coordinate representing the origin of rotation, eg. (0, 0, 0)

    axis : Axis
        Axis of rotation, eg. (0, 0, 1)

    stationary_patches : List[str]
        A list of static patch names of an interface

    rotating_patches : List[str]
        A list of dynamic patch names of an interface

    volume_name : str
        A list of dynamic volume zones related to the above {omega, centerOfRotation, axisOfRotation}

    name: str, optional
        Name of slidingInterface

    parent_volume_name : str, optional
        Name of the volume zone that the rotating reference frame is contained in, used to compute the acceleration in
        the nested rotating reference frame

    theta_radians : str, optional
        Expression for rotation angle (in radians) as a function of time

    theta_degrees : str, optional
        Expression for rotation angle (in degrees) as a function of time

    omega : Union[float, Omega], optional
        Rotating speed without or with unit, eg. 1.0, (1.0, 'rad/s'), (1.0, 'deg/s'), (1.0, 'non-dim'). If no unit
        provided, non-dimensional is assumed.

    rpm : float, optional
        Rotating speed in revolutions per minute (RPM)

    omega_radians
        Nondimensional rotating speed, radians/nondim-unit-time

    omega_degrees
        Nondimensional rotating speed, degrees/nondim-unit-time

    is_dynamic
        Whether rotation of this interface is dictated by userDefinedDynamics


    Returns
    -------
    :class:`SlidingInterface`
        An instance of the component class SlidingInterface.

    Example
    -------
    >>> si = SlidingInterface(
            center=(0, 0, 0),
            axis=(0, 0, 1),
            stationary_patches=['patch1'],
            rotating_patches=['patch2'],
            volume_name='volume1',
            omega=(1, 'rad/s')
        )
    """

    center: Coordinate = pd.Field(alias="centerOfRotation")
    axis: Axis = pd.Field(alias="axisOfRotation")
    stationary_patches: List[str] = pd.Field(alias="stationaryPatches")
    rotating_patches: List[str] = pd.Field(alias="rotatingPatches")
    volume_name: str = pd.Field(alias="volumeName")
    parent_volume_name: Optional[str] = pd.Field(alias="parentVolumeName")
    name: Optional[str] = pd.Field(alias="interfaceName")
    theta_radians: Optional[str] = pd.Field(alias="thetaRadians")
    theta_degrees: Optional[str] = pd.Field(alias="thetaDegrees")
    omega: Optional[Union[float, Omega]] = pd.Field()
    omega_radians: Optional[float] = pd.Field(alias="omegaRadians")
    omega_degrees: Optional[float] = pd.Field(alias="omegaDegrees")
    rpm: Optional[float]
    is_dynamic: Optional[bool] = pd.Field(alias="isDynamic")

    # pylint: disable=no-self-argument
    @pd.validator("omega", pre=True, always=True)
    def validate_omega(cls, v):
        """Validator for omega"""
        if isinstance(v, tuple):
            return Omega(v=v[0], unit=v[1])
        return v

    # pylint: disable=invalid-name
    @export_to_flow360
    def to_flow360_json(self, return_json: bool = True, mesh_unit_length=None, C_inf=None):
        """
        returns flow360 formatted json
        """
        self.perform_non_dimensionalisation(mesh_unit_length, C_inf)
        if return_json:
            return self.json()
        return None

    # pylint: disable=invalid-name
    def perform_non_dimensionalisation(self, mesh_unit_length, C_inf):
        """
        performs non-dimensionalisation
        """
        if self.omega:
            if isinstance(self.omega, float):
                self.omega_radians = self.omega
            elif self.omega.unit == "rad/s":
                self.omega_radians = self.omega.v * get_time_non_dim_unit(
                    mesh_unit_length, C_inf, extra_msg="when using rad/s unit for omega."
                )
            elif self.omega.unit == "deg/s":
                self.omega_degrees = self.omega.v * get_time_non_dim_unit(
                    mesh_unit_length, C_inf, extra_msg="when using deg/s unit for omega."
                )
            elif self.omega.unit == "non-dim":
                self.omega_degrees = self.omega.v

        if self.rpm:
            omega = self.rpm * (2 * math.pi) / 60
            self.omega_radians = omega * get_time_non_dim_unit(
                mesh_unit_length, C_inf, "when using rpm."
            )

    # pylint: disable=missing-class-docstring,too-few-public-methods
    class Config(Flow360BaseModel.Config):
        exclude_on_flow360_export = ["omega", "rpm"]
        require_one_of = [
            "omega",
            "rpm",
            "omega_radians",
            "omega_degrees",
            "theta_radians",
            "theta_degrees",
            "is_dynamic",
        ]


class MeshSlidingInterface(Flow360BaseModel):
    """
    Sliding interface component
    """

    stationary_patches: List[str] = pd.Field(alias="stationaryPatches")
    rotating_patches: List[str] = pd.Field(alias="rotatingPatches")
    axis: Axis = pd.Field(alias="axisOfRotation")
    center: Coordinate = pd.Field(alias="centerOfRotation")

    @classmethod
    def from_case_sliding_interface(cls, si: SlidingInterface):
        """
        create mesh sliding interface (for Flow360Mesh.json) from case params SlidingInterface
        """
        return cls(
            stationary_patches=si.stationary_patches,
            rotating_patches=si.rotating_patches,
            axis=si.axis,
            center=si.center,
        )


class TimeSteppingCFL(Flow360BaseModel):
    """
    CFL for time stepping component
    """

    initial: Optional[int] = pd.Field()
    final: Optional[int] = pd.Field()
    ramp_steps: Optional[int] = pd.Field(alias="rampSteps")

    @classmethod
    def default_steady(cls):
        """
        returns default steady CFL settings
        """
        return cls(initial=5, final=200, ramp_steps=40)

    @classmethod
    def default_unsteady(cls):
        """
        returns default unsteady CFL settings
        """
        return cls(initial=1, final=1e6, ramp_steps=30)


# pylint: disable=E0213
class TimeStepping(Flow360BaseModel):
    """
    Time stepping component
    """

    physical_steps: Optional[int] = pd.Field(alias="physicalSteps")
    max_pseudo_steps: Optional[int] = pd.Field(alias="maxPseudoSteps")
    time_step_size: Optional[
        Union[pd.confloat(gt=0, allow_inf_nan=False), TimeStep, Literal["inf"]]
    ] = pd.Field(alias="timeStepSize", default="inf")
    CFL: Optional[TimeSteppingCFL] = pd.Field()

    @classmethod
    def default_steady(cls):
        """
        returns default steady settings
        """
        return cls(
            physical_steps=1,
            time_step_size="inf",
            max_pseudo_steps=2000,
            CFL=TimeSteppingCFL.default_steady(),
        )

    @classmethod
    def default_unsteady(cls, physical_steps, time_step_size):
        """
        returns default unsteady settings
        """
        return cls(
            physical_steps=physical_steps,
            time_step_size=time_step_size,
            max_pseudo_steps=40,
            CFL=TimeSteppingCFL.default_unsteady(),
        )

    # pylint: disable=invalid-name
    @export_to_flow360
    def to_flow360_json(self, return_json: bool = True, mesh_unit_length=None, C_inf=None):
        """
        returns flow360 formatted json
        """
        self.perform_non_dimensionalisation(mesh_unit_length, C_inf)
        if return_json:
            return self.json()
        return None

    # pylint: disable=invalid-name
    def perform_non_dimensionalisation(self, mesh_unit_length, C_inf):
        """
        performs non-dimensionalisation
        """
        if isinstance(self.time_step_size, TimeStep):
            if self.time_step_size.is_second():
                self.time_step_size = self.time_step_size.v / get_time_non_dim_unit(
                    mesh_unit_length, C_inf, extra_msg="when using time_step_size in seconds."
                )
            elif self.time_step_size.unit == "deg":
                raise Flow360NotImplementedError("Time step size in 'deg' is not yet implemented.")

    @pd.validator("time_step_size", pre=True, always=True)
    def check_time_step_size(cls, value):
        """time step validator"""
        if isinstance(value, tuple):
            return TimeStep(v=value[0], unit=value[1])
        return value


class _GenericBoundaryWrapper(Flow360BaseModel):
    v: BoundaryType


class Boundaries(Flow360SortableBaseModel):
    """:class:`Boundaries` class for setting up Boundaries

    Parameters
    ----------
    <boundary_name> : BoundaryType
        Supported boundary types: Union[NoSlipWall, SlipWall, FreestreamBoundary, IsothermalWall,
                                        SubsonicOutflowPressure, SubsonicOutflowMach, SubsonicInflow,
                                        SlidingInterfaceBoundary, WallFunction, MassInflow, MassOutflow]

    Returns
    -------
    :class:`Boundaries`
        An instance of the component class Boundaries.

    Example
    -------
    >>> boundaries = Boundaries(
            wing=NoSlipWall(),
            symmetry=SlipWall(),
            freestream=FreestreamBoundary()
        )
    """

    @pd.root_validator(pre=True)
    def validate_boundary(cls, values):
        """Validator for boundary list section

        Raises
        ------
        ValidationError
            When boundary is incorrect
        """
        for key, v in values.items():
            try:
                values[key] = _GenericBoundaryWrapper(v=v).v
            except Exception as exc:
                raise ValidationError(
                    f"{v} (type={type(v)}) is not any of supported boundary types."
                ) from exc
        return values


class Geometry(Flow360BaseModel):
    """
    Geometry component
    """

    ref_area: Optional[float] = pd.Field(alias="refArea")
    moment_center: Optional[Coordinate] = pd.Field(alias="momentCenter")
    moment_length: Optional[MomentLengthType] = pd.Field(alias="momentLength")

    mesh_unit_length: Optional[PositiveFloat] = pd.Field(alias="meshUnitLength")
    mesh_unit: Optional[Literal["m", "cm", "mm", "inch", "feet"]] = pd.Field(alias="meshUnit")

    def get_mesh_unit_length(self):
        """Returns mesh unit length in meters. Needs one of [mesh_unit_length, mesh_unit] to be specified

        Returns
        -------
        float
            mesh unit length in meters
        """
        if self.mesh_unit_length:
            return self.mesh_unit_length
        if self.mesh_unit:
            return self.mesh_unit_length_in_meter(self.mesh_unit)
        return None

    def mesh_unit_length_in_meter(self, unit: Literal["m", "cm", "mm", "inch", "feet"]):
        """unit length in meters

        Parameters
        ----------
        unit : Literal[&quot;m&quot;, &quot;cm&quot;, &quot;mm&quot;, &quot;inch&quot;, &quot;feet&quot;]
            Unit name

        Returns
        -------
        float
            unit length in meters
        """
        in_meter = {"m": 1, "cm": 0.01, "mm": 0.001, "inch": 0.0254, "feet": 0.3048}
        return in_meter[unit]

    # pylint: disable=missing-class-docstring,too-few-public-methods
    class Config(Flow360BaseModel.Config):
        exclude_on_flow360_export = {"mesh_unit", "mesh_unit_length"}


class Freestream(Flow360BaseModel):
    """
    Freestream component
    """

    Reynolds: Optional[PositiveFloat] = pd.Field()
    Mach: Optional[PositiveFloat] = pd.Field()
    MachRef: Optional[PositiveFloat] = pd.Field()
    mu_ref: Optional[PositiveFloat] = pd.Field(alias="muRef")
    temperature: PositiveFloat = pd.Field(alias="Temperature")
    density: Optional[PositiveFloat]
    speed: Optional[Union[Velocity, PositiveFloat]]
    alpha: Optional[float] = pd.Field(alias="alphaAngle")
    beta: Optional[float] = pd.Field(alias="betaAngle", default=0)
    turbulentViscosityRatio: Optional[PositiveFloat]

    @pd.validator("speed", pre=True, always=True)
    def validate_speed(cls, v):
        """speed validator"""
        if isinstance(v, tuple):
            return Velocity(v=v[0], unit=v[1])
        return v

    def get_C_inf(self):
        """returns speed of sound based on model's temperature"""
        return self._speed_of_sound_from_temperature(self.temperature)

    @classmethod
    def _speed_of_sound_from_temperature(cls, T: float):
        """calculates speed of sound"""
        return math.sqrt(1.4 * constants.R * T)

    # pylint: disable=invalid-name
    def _mach_from_speed(self, speed):
        if speed:
            C_inf = self.get_C_inf()
            if isinstance(self.speed, Velocity):
                self.Mach = self.speed.v / C_inf
            else:
                self.Mach = self.speed / C_inf

    @classmethod
    def from_speed(
        cls,
        speed: Union[Velocity, PositiveFloat] = None,
        temperature: PositiveFloat = 288.15,
        density: PositiveFloat = 1.225,
        **kwargs,
    ) -> Freestream:
        """class: `Freestream`

        Parameters
        ----------
        speed : Union[Velocity, PositiveFloat]
            Value for freestream speed, e.g., (100.0, 'm/s'). If no unit provided, meters per second is assumed.
        temperature : PositiveFloat, optional
            temeperature, by default 288.15
        density : PositiveFloat, optional
            density, by default 1.225

        Returns
        -------
        :class: `Freestream`
            returns Freestream object

        Example
        -------
        >>> fs = Freestream.from_speed(speed=(10, "m/s"))
        """
        assert speed
        fs = cls(temperature=temperature, speed=speed, density=density, **kwargs)
        fs._mach_from_speed(fs.speed)
        return fs

    @export_to_flow360
    def to_flow360_json(self, return_json: bool = True, mesh_unit_length=None):
        """
        returns flow360 formatted json
        """
        if self.Reynolds is None and self.mu_ref is None:
            if self.density is None:
                raise ConfigError("density is required.")
            viscosity = 1.458e-6 * pow(self.temperature, 1.5) / (self.temperature + 110.4)
            self.mu_ref = (
                viscosity
                / (self.density * self.get_C_inf())
                / get_length_non_dim_unit(mesh_unit_length)
            )

        if self.speed:
            self._mach_from_speed(self.speed)

        if return_json:
            return self.json()
        return None

    # pylint: disable=missing-class-docstring,too-few-public-methods
    class Config(Flow360BaseModel.Config):
        exclude_on_flow360_export = {"speed", "density"}
        require_one_of = ["Mach", "speed"]


class GenericSolverSettings(Flow360BaseModel):
    """:class:`GenericSolverSettings` class"""

    absolute_tolerance: Optional[PositiveFloat] = pd.Field(alias="absoluteTolerance")
    relative_tolerance: Optional[float] = pd.Field(alias="relativeTolerance")
    linear_iterations: Optional[PositiveInt] = pd.Field(alias="linearIterations")
    update_jacobian_frequency: Optional[PositiveInt] = pd.Field(alias="updateJacobianFrequency")
    equation_eval_frequency: Optional[PositiveInt] = pd.Field(alias="equationEvalFrequency")
    max_force_jac_update_physical_steps: Optional[NonNegativeInt] = pd.Field(
        alias="maxForceJacUpdatePhysicalSteps"
    )
    order_of_accuracy: Optional[Literal[1, 2]] = pd.Field(alias="orderOfAccuracy")
    kappaMUSCL: Optional[pd.confloat(ge=-1, le=1)] = pd.Field()


class NavierStokesSolver(GenericSolverSettings):
    """:class:`NavierStokesSolver` class for setting up Navier-Stokes solver

    Parameters
    ----------

    absoluteTolerance :
        Tolerance for the NS residual, below which the solver goes to the next physical step

    relativeTolerance :
        Tolerance to the relative residual, below which the solver goes to the next physical step. Relative residual is
        defined as the ratio of the current pseudoStep’s residual to the maximum residual present in the first
        10 pseudoSteps within the current physicalStep. NOTE: relativeTolerance is ignored in steady simulations and
        only absoluteTolerance is used as the convergence criterion

    CFLMultiplier :
        Factor to the CFL definitions defined in “timeStepping” section

    kappaMUSCL :
        Kappa for the MUSCL scheme, range from [-1, 1], with 1 being unstable. The default value of -1 leads to a 2nd
        order upwind scheme and is the most stable. A value of 0.33 leads to a blended upwind/central scheme and is
        recommended for low subsonic flows leading to reduced dissipation

    linearIterations :
        Number of linear solver iterations

    updateJacobianFrequency :
        Frequency at which the jacobian is updated.

    equationEvalFrequency :
        Frequency at which to update the NS equation in loosely-coupled simulations

    maxForceJacUpdatePhysicalSteps :
        When which physical steps, the jacobian matrix is updated every pseudo step

    orderOfAccuracy :
        Order of accuracy in space

    limitVelocity :
        Limiter for velocity

    limitPressureDensity :
        Limiter for pressure and density


    Returns
    -------
    :class:`NavierStokesSolver`
        An instance of the component class NavierStokesSolver.

    Example
    -------
    >>> ns = NavierStokesSolver(absolute_tolerance=1e-10)
    """

    CFL_multiplier: Optional[PositiveFloat] = pd.Field(alias="CFLMultiplier")
    limit_velocity: Optional[bool] = pd.Field(alias="limitVelocity")
    limit_pressure_density: Optional[bool] = pd.Field(alias="limitPressureDensity")


class TurbulenceModelModelType(str, Enum):
    """Turbulence model type"""

    SA = "SpalartAllmaras"
    SST = "kOmegaSST"
    NONE = "None"


class TurbulenceModelConstants(Flow360BaseModel):
    """TurbulenceModelConstants"""

    C_DES: Optional[float]
    C_d: Optional[float]
    C_DES1: Optional[float]
    C_DES2: Optional[float]
    C_d1: Optional[float]
    C_d2: Optional[float]


class TurbulenceModelSolver(GenericSolverSettings):
    """:class:`TurbulenceModelSolver` class for setting up turbulence model solver

    Parameters
    ----------

    model_type :
        Turbulence model type can be: “SpalartAllmaras”, “kOmegaSST” or "None"

    absoluteTolerance :
        Tolerance for the NS residual, below which the solver goes to the next physical step

    relativeTolerance :
        Tolerance to the relative residual, below which the solver goes to the next physical step. Relative residual is
        defined as the ratio of the current pseudoStep’s residual to the maximum residual present in the first
        10 pseudoSteps within the current physicalStep. NOTE: relativeTolerance is ignored in steady simulations and
        only absoluteTolerance is used as the convergence criterion

    linearIterations :
        Number of linear solver iterations

    updateJacobianFrequency :
        Frequency at which the jacobian is updated.

    equationEvalFrequency :
        Frequency at which to update the NS equation in loosely-coupled simulations

    maxForceJacUpdatePhysicalSteps :
        When which physical steps, the jacobian matrix is updated every pseudo step

    orderOfAccuracy :
        Order of accuracy in space

    reconstruction_gradient_limiter :
        The strength of gradient limiter used in reconstruction of solution variables at the faces (specified in the
        range [0.0, 2.0]). 0.0 corresponds to setting the gradient equal to zero, and 2.0 means no limiting.

    rotation_correction : bool, optional
        Rotation correction for the turbulence model. Only support for SpalartAllmaras

    quadratic_constitutive_relation : bool, optional
        Use quadratic constitutive relation for turbulence shear stress tensor instead of Boussinesq Approximation

    DDES : bool, optional
        Enables Delayed Detached Eddy Simulation. Supported for both SpalartAllmaras and kOmegaSST turbulence models,
        with and without AmplificationFactorTransport transition model enabled.

    grid_size_for_LES : Literal['maxEdgeLength', 'meanEdgeLength'], optional
        Specifes the length used for the computation of LES length scale. The allowed inputs are "maxEdgeLength"
        (default) and "meanEdgeLength"

    model_constants :
        Here, user can change the default values used for DDES coefficients in the solver:
        SpalartAllmaras: "C_DES" (= 0.72), "C_d" (= 8.0)
        kOmegaSST: "C_DES1" (= 0.78), "C_DES2" (= 0.61), "C_d1" (= 20.0), "C_d2" (= 3.0)
        (values shown in the parentheses are the default values used in Flow360)
        An example with kOmegaSST mode would be: {"C_DES1": 0.85, "C_d1": 8.0}

    Returns
    -------
    :class:`TurbulenceModelSolver`
        An instance of the component class TurbulenceModelSolver.

    Example
    -------
    >>> ts = TurbulenceModelSolver(model_type='SA', absolute_tolerance=1e-10)
    """

    model_type: TurbulenceModelModelType = pd.Field(
        alias="modelType", default=TurbulenceModelModelType.SA
    )
    reconstruction_gradient_limiter: Optional[pd.confloat(ge=0, le=2)] = pd.Field(
        alias="reconstructionGradientLimiter"
    )
    rotation_correction: Optional[bool] = pd.Field(alias="rotationCorrection")
    quadratic_constitutive_relation: Optional[bool] = pd.Field(
        alias="quadraticConstitutiveRelation"
    )
    DDES: Optional[bool]
    grid_size_for_LES: Optional[Literal["maxEdgeLength", "meanEdgeLength"]] = pd.Field(
        alias="gridSizeForLES"
    )
    model_constants: Optional[TurbulenceModelConstants] = pd.Field(alias="modelConstants")

    @pd.validator("model_type", pre=True, always=True)
    def validate_model_type(cls, v):
        """Turbulence model validator"""
        if v == "SA":
            return TurbulenceModelModelType.SA
        if v == "SST":
            return TurbulenceModelModelType.SST
        if v == "None":
            return TurbulenceModelModelType.NONE
        return v


class Flow360Params(Flow360BaseModel):
    """
    Flow360 solver parameters
    """

    geometry: Optional[Geometry] = pd.Field()
    boundaries: Optional[Boundaries] = pd.Field()
    time_stepping: Optional[TimeStepping] = pd.Field(alias="timeStepping", default=TimeStepping())
    sliding_interfaces: Optional[List[SlidingInterface]] = pd.Field(alias="slidingInterfaces")
    navier_stokes_solver: Optional[NavierStokesSolver] = pd.Field(alias="navierStokesSolver")
    turbulence_model_solver: Optional[TurbulenceModelSolver] = pd.Field(
        alias="turbulenceModelSolver"
    )
    transition_model_solver: Optional[Dict] = pd.Field(alias="transitionModelSolver")
    freestream: Optional[Freestream] = pd.Field()
    bet_disks: Optional[List] = pd.Field(alias="betDisks")
    actuator_disks: Optional[List] = pd.Field(alias="actuatorDisks")
    surface_output: Optional[Dict] = pd.Field(alias="surfaceOutput")
    volume_output: Optional[Dict] = pd.Field(alias="volumeOutput")
    slice_output: Optional[Dict] = pd.Field(alias="sliceOutput")

    # pylint: disable=invalid-name
    def _get_non_dimensionalisation(self):
        mesh_unit_length, C_inf = None, None
        if self.geometry:
            mesh_unit_length = _get_value_or_none(self.geometry.get_mesh_unit_length)
        if self.freestream:
            C_inf = _get_value_or_none(self.freestream.get_C_inf)
        return mesh_unit_length, C_inf

    # pylint: disable=arguments-differ
    def to_flow360_json(self):
        """
        returns flow360 formatted json
        """
        mesh_unit_length, C_inf = self._get_non_dimensionalisation()
        if self.sliding_interfaces:
            for s in self.sliding_interfaces:
                s.to_flow360_json(mesh_unit_length=mesh_unit_length, C_inf=C_inf, return_json=False)

        if not self.freestream:
            raise ConfigError("freestream required")

        if not self.geometry:
            self.geometry = Geometry()

        if not self.navier_stokes_solver:
            self.navier_stokes_solver = NavierStokesSolver()

        if not self.turbulence_model_solver:
            self.turbulence_model_solver = TurbulenceModelSolver()

        self.freestream.to_flow360_json(mesh_unit_length=mesh_unit_length, return_json=False)
        self.geometry.to_flow360_json(return_json=False)
        return self.json()

    def append(self, params: Flow360Params, overwrite: bool = False):
        if not isinstance(params, Flow360Params):
            raise ValueError("params must be type of Flow360Params")
        super().append(params=params, overwrite=overwrite)

    @classmethod
    def default(cls, steady: bool = True, solver_version: str = None) -> Flow360Params:
        """
        return default case settings
        """
        raise Flow360NotImplementedError("Default flow360 params are not yet implemented.")


class Flow360MeshParams(Flow360BaseModel):
    """
    Flow360 mesh parameters
    """

    boundaries: MeshBoundary = pd.Field()
    sliding_interfaces: Optional[List[MeshSlidingInterface]] = pd.Field(alias="slidingInterfaces")