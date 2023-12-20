from lib.real_oven import RealOven
from lib.simulated_oven import SimulatedOven


class OvenFactory:
    REAL = 'REAL'
    SIMULATED = 'SIMULATED'

    @staticmethod
    def create_oven(type):
        if type == OvenFactory.REAL:
            return RealOven()
        elif type == OvenFactory.SIMULATED:
            return SimulatedOven()
        else:
            raise Exception(f"Invalid oven type: {type}")
