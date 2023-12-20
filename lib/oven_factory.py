from lib.real_oven import RealOven
from lib.simulated_oven import SimulatedOven


class OvenFactory:
    REAL = 'REAL'
    SIMULATED = 'SIMULATED'

    @staticmethod
    def create_oven(type, configuration):
        if type == OvenFactory.REAL:
            return RealOven(configuration)
        elif type == OvenFactory.SIMULATED:
            return SimulatedOven(configuration)
        else:
            raise Exception(f"Invalid oven type: {type}")
