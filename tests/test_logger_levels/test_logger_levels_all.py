import pytest
from numerous.engine.model import Model
from numerous.engine.simulation import Simulation
from numerous.utils.logger_levels import LoggerLevel
from numerous.multiphysics.equation_base import EquationBase
from numerous.multiphysics.equation_decorators import Equation
from numerous.engine.system.item import Item
from numerous.engine.system.subsystem import Subsystem
from numerous.engine.simulation.solvers.base_solver import solver_types
import numpy as np

INFO = LoggerLevel.INFO
DEBUG = LoggerLevel.DEBUG
ALL = LoggerLevel.ALL


@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    import shutil
    shutil.rmtree('../tmp', ignore_errors=True)
    yield


class TestLogItem1(Item, EquationBase):
    def __init__(self, tag='testlogitem1'):
        super(TestLogItem1, self).__init__(tag)
        self.t1 = self.create_namespace('t1')
        self.add_state('v', 0, logger_level=INFO)
        self.add_state('s', 0.5, logger_level=DEBUG)
        self.add_parameter('p', 1, logger_level=ALL)

        self.t1.add_equations([self])
        return

    @Equation()
    def eval(self, scope):
        scope.v_dot = 1
        scope.s_dot = -2 / ((np.exp(scope.v) + np.exp(-scope.v)) ** 2)


class TestLogSubsystem1(Subsystem):
    def __init__(self, tag='testlogsubsystem1'):
        super().__init__(tag)
        item = TestLogItem1()
        self.register_items([item])


def sigmoidlike(t):
    return 1 / (1 + np.exp(2 * t))


@pytest.mark.parametrize("solver", solver_types)
@pytest.mark.parametrize("use_llvm", [True, False])
def test_logger_levels(solver, use_llvm):
    num = 100
    t_stop = 100
    t_start = 0
    sys = TestLogSubsystem1()
    model = Model(sys, logger_level=ALL, use_llvm=use_llvm)
    tvec = np.linspace(t_start, t_stop, num + 1, dtype=np.float64)
    sim = Simulation(model, t_start=t_start, t_stop=t_stop, num=num, num_inner=1, solver_type=solver,
                     rtol=1e-8, atol=1e-8)
    sim.solve()

    df = sim.model.historian_df

    s_analytic = sigmoidlike(tvec)

    prefix = 'testlogsubsystem1.testlogitem1.t1'
    p = f"{prefix}.p"
    v = f"{prefix}.v"
    s = f"{prefix}.s"

    expected_results = {v: tvec, p: np.ones(num + 1), s: s_analytic}

    for k, v in expected_results.items():
        assert pytest.approx(v, abs=1e-5) == df.get(k), "expected results do not match actual results"
