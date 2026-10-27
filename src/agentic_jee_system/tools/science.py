"""Explicit small numerical domain registry. Inputs use SI unless stated."""
import json
import math


def science(operation: str, values: dict[str, float]) -> dict[str, float]:
    """Validate exact parameter names before computing a supported formula."""
    signatures = {
        "linear_equation": {"a", "b", "c"},
        "kinetic_energy": {"mass", "velocity"},
        "force_motion": {"mass", "force", "time", "initial_velocity"},
        "centripetal_acceleration": {"radius", "angular_velocity"},
        "moles": {"mass_g", "molar_mass_g_mol"},
        "molarity": {"moles", "volume_l"},
        "ideal_gas_moles": {"pressure_pa", "volume_m3", "temperature_k"},
        "kmh_to_ms": {"speed"},
    }
    if operation not in signatures or not isinstance(values, dict) or set(values) != signatures[operation]:
        raise ValueError("Unknown operation or incorrect parameter names.")
    for value in values.values():
        if (isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value) or abs(value) > 1e30 or 0 < abs(value) < 1e-30):
            raise ValueError("Parameters must be zero or finite real numbers with magnitude between 1e-30 and 1e30.")
    positive = {"mass", "molar_mass_g_mol", "volume_l", "temperature_k"}
    nonnegative = {"mass_g", "radius", "time", "moles", "pressure_pa", "volume_m3"}
    if any(value <= 0 for key, value in values.items() if key in positive):
        raise ValueError("Mass, molar mass, temperature and concentration volume must be positive.")
    if any(value < 0 for key, value in values.items() if key in nonnegative):
        raise ValueError("Negative physical magnitude is unsupported.")
    v = values
    if operation == "linear_equation":
        if not v["a"]:
            raise ValueError("Equation a*x+b=c requires nonzero a.")
        return {"x": (v["c"] - v["b"]) / v["a"]}
    if operation == "kinetic_energy":
        return {"energy_j": 0.5 * v["mass"] * v["velocity"] ** 2}
    if operation == "force_motion":
        acceleration = v["force"] / v["mass"]
        velocity = v["initial_velocity"] + acceleration * v["time"]
        return {"acceleration_ms2": acceleration, "velocity_ms": velocity,
                "energy_j": 0.5 * v["mass"] * velocity ** 2}
    if operation == "centripetal_acceleration":
        return {"acceleration_ms2": v["angular_velocity"] ** 2 * v["radius"]}
    if operation == "moles":
        return {"moles": v["mass_g"] / v["molar_mass_g_mol"]}
    if operation == "molarity":
        return {"molarity_mol_l": v["moles"] / v["volume_l"]}
    if operation == "ideal_gas_moles":
        return {"moles": v["pressure_pa"] * v["volume_m3"] / (8.314462618 * v["temperature_k"])}
    return {"speed_ms": v["speed"] / 3.6}


def make_science_tool(audit):
    from crewai.tools import tool

    @tool("science_calculator")
    def science_calculator(operation: str, values_json: str) -> str:
        """Compute a named formula with exact JSON parameters:
        linear_equation(a,b,c) solves a*x+b=c;
        kinetic_energy(mass,velocity); force_motion(mass,force,time,initial_velocity);
        centripetal_acceleration(radius,angular_velocity); moles(mass_g,molar_mass_g_mol);
        molarity(moles,volume_l); ideal_gas_moles(pressure_pa,volume_m3,temperature_k);
        kmh_to_ms(speed). Use SI units except parameter names explicitly specifying g or l.
        """
        try:
            if len(values_json) > 1000:
                raise ValueError("Too many parameters.")
            result = science(operation, json.loads(values_json))
            audit.append({"tool": "science_calculator", "operation": operation,
                          "success": True, "result": result})
            return json.dumps(result)
        except (ValueError, TypeError, ArithmeticError):
            audit.append({"tool": "science_calculator", "success": False})
            return "Invalid operation or parameters. Check tool signature and units."

    return science_calculator
