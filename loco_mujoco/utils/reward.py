import numpy as np
from loco_mujoco.utils.math import mat2angle_xy


class RewardInterface:
    """
    Interface to specify a reward function.

    """

    def __call__(self, state, action, next_state, absorbing):
        """
        Compute the reward.

        Args:
            state (np.ndarray): last state;
            action (np.ndarray): applied action;
            next_state (np.ndarray): current state.

        Returns:
            The reward for the current transition.

        """
        raise NotImplementedError

    def reset_state(self):
        """
        Reset the state of the object.

        """
        pass


class NoReward(RewardInterface):
    """
    A reward function that returns always 0.

    """

    def __call__(self, state, action, next_state, absorbing):
        return 0


class PosReward(RewardInterface):

    def __init__(self, pos_idx):
        self._pos_idx = pos_idx

    def __call__(self, state, action, next_state, absorbing):
        pos = state[self._pos_idx]
        return pos


class CustomReward(RewardInterface):

    def __init__(self, reward_callback=None):
        self._reward_callback = reward_callback

    def __call__(self, state, action, next_state, absorbing):
        if self._reward_callback is not None:
            return self._reward_callback(state, action, next_state)
        else:
            return 0


class TargetVelocityReward(RewardInterface):

    def __init__(self, target_velocity, x_vel_idx):
        self._target_vel = target_velocity
        self._x_vel_idx = x_vel_idx

    def __call__(self, state, action, next_state, absorbing):
        x_vel = state[self._x_vel_idx]
        return np.exp(- np.square(x_vel - self._target_vel))


class MultiTargetVelocityReward(RewardInterface):

    def __init__(self, target_velocity, x_vel_idx, env_id_len, scalings):
        self._target_vel = target_velocity
        self._env_id_len = env_id_len
        self._scalings = scalings
        self._x_vel_idx = x_vel_idx

    def __call__(self, state, action, next_state, absorbing):
        x_vel = state[self._x_vel_idx]
        env_id = state[-self._env_id_len:]

        # convert binary array to index
        ind = np.packbits(env_id.astype(int), bitorder='big') >> (8 - env_id.shape[0])
        ind = ind[0]
        scaling = self._scalings[ind]

        # calculate target vel
        target_vel = self._target_vel * scaling

        return np.exp(- np.square(x_vel - target_vel))


class VelocityVectorReward(RewardInterface):

    def __init__(self, x_vel_idx, y_vel_idx, rot_mat_idx, goal_vel_idx):
        self._x_vel_idx = x_vel_idx
        self._y_vel_idx = y_vel_idx
        self._rot_mat_idx = rot_mat_idx
        self._goal_vel_idx = goal_vel_idx

    def __call__(self, state, action, next_state, absorbing):

        # get current velocity vector in x-y-plane
        curr_velocity_xy = np.array([state[self._x_vel_idx], state[self._y_vel_idx]])

        # get desired velocity vector in x-y-plane
        rot_mat = state[self._rot_mat_idx].reshape((3, 3))
        angle = mat2angle_xy(rot_mat)
        angle -= np.pi/2
        norm_x = np.cos(angle)
        norm_y = np.sin(angle)
        des_vel = state[self._goal_vel_idx] * np.array([norm_x, norm_y])

        return np.exp(-5.0*np.linalg.norm(curr_velocity_xy - des_vel))


class OutOfBoundsActionCost(RewardInterface):

    def __init__(self, lower_bound, upper_bound, reward_scale=1.0, const_cost=0.0, func_type='abs'):
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.reward_scale = reward_scale
        self.const_cost = const_cost

        if func_type == 'abs':
            self.func = np.abs
        elif func_type == 'squared':
            self.func = np.square
        else:
            raise Exception(f'{func_type} is not a valid function type!')

    def __call__(self, state, action, next_state, absorbing):
        lower_cost = (self.lower_bound - action + self.const_cost) * (action < self.lower_bound)
        upper_cost = (action - self.upper_bound + self.const_cost) * (action > self.upper_bound)
        return -1 * self.reward_scale * np.sum(self.func(lower_cost + upper_cost))


class ActionCost(RewardInterface):

    def __init__(self, action_mean, reward_scale=1.0, func_type='abs'):
        self.action_mean = action_mean
        self.reward_scale = reward_scale

        if func_type == 'abs':
            self.func = np.abs
        elif func_type == 'squared':
            self.func = np.square
        else:
            raise Exception(f'{func_type} is not a valid function type!')

    def __call__(self, state, action, next_state, absorbing):
        return -1 * self.reward_scale * np.sum(self.func(action - self.action_mean))


class InBoundsBonus(RewardInterface):

    def __init__(self, lower_bound, upper_bound, reward_scale=1.0, bonus_val=1.0):
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.reward_scale = reward_scale
        self.bonus_val = bonus_val

    def __call__(self, state, action, next_state, absorbing):
        bonus = self.bonus_val * ((self.upper_bound > action) * (action > self.lower_bound))
        return self.reward_scale * np.sum(bonus)


class ModulationDifferencePenalty(RewardInterface):

    def __init__(self, action_space_modulator, cycle_percentage_predictors,
                 reward_scale=1.0, func_type='abs'):
        self.cycle_percentage_predictors = cycle_percentage_predictors
        self.action_space_modulator = action_space_modulator

        self.cycle_progress = np.zeros(len(cycle_percentage_predictors))

        self.reward_scale = reward_scale

        if func_type == 'abs':
            self.func = np.abs
        elif func_type == 'squared':
            self.func = np.square
        else:
            raise Exception(f'{func_type} is not a valid function type!')

    def __call__(self, state, action, next_state, absorbing):
        self.cycle_progress = [channel.predict_cycle_percentage(state) for channel in
                               self.cycle_percentage_predictors]

        modulated_action = self.action_space_modulator.modulate_action(action, self.cycle_progress)

        modulated_action_diff = action - modulated_action

        return -1 * self.reward_scale * np.sum(self.func(modulated_action_diff))

