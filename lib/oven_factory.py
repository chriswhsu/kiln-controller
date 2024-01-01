from lib.real_oven import RealOven
from lib.simulated_oven import SimulatedOven


class OvenFactory:
    REAL = 'REAL'
    SIMULATED = 'SIMULATED'

    @staticmethod
    def create_oven(oven_type, configuration):
        if oven_type == OvenFactory.REAL:
            return RealOven(configuration)
        elif oven_type == OvenFactory.SIMULATED:
            return SimulatedOven(configuration)
        else:
            raise Exception(f"Invalid oven type: {oven_type}")
