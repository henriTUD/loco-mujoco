import numpy as np

from loco_mujoco import LocoEnv


def experiment(seed=0):

    np.random.seed(seed)

    mdp = LocoEnv.make("UnitreeA1.simple")

    mdp.play_trajectory_from_velocity(n_steps_per_episode=250)


if __name__ == '__main__':
    experiment()
