"""File Name: ddpg.py"""
"""
Description: 
    Project Name: xxx
    Project Leader: Yuanliang Li
    File Author: Yuanliang Li
    Creation Time: xx
    Latest Updating Time: xx
    Techniques: DDPG + Prioritized replay + Delayed update + Policy noise
    Environment: xxx
    Package requirements: Numpy 1.17.3, Pytorch-cpu 1.1.0   
"""


import torch
import random
import numpy as np
import torch.nn as nn
import torch.optim as optim
from collections import deque
import torch.nn.functional as F
import math


class DDPG:

    def __init__(self,env):

        # training time related
        self.train_time_ratio = 0.5 # the percentage of the time used for training
        self.train_stop_seconds = env.duration_seconds * self.train_time_ratio
        self.time_now = 0 # unit: second


        # some learning parameters
        self.lr_a = 1e-3
        self.lr_c = 1e-3
        self.gamma = 0.97
        self.tao = 1e-2
        self.hidden_size_a = 30
        self.hidden_size_c = 30
        self.actor_update_fre = 6
        self.update_count = 0

        # set noise parameters for exploration and target action
        self.noise_decay_mode = 'quadratic'  # 'quadratic', 'linear', ' constant'
        self.noise_intensity_max = 0.6
        self.noise_intensity_min = 0.1
        self.noise_policy_intensity = 0.1

        # set CPU or GPU
        self.device = torch.device('cuda:0') if torch.cuda.is_available() else torch.device('cpu') # torch device

        # set the random seeds
        torch.manual_seed(1943)
        np.random.seed(1943)

        # create neural networks for actors, critics, target actors, target critics
        self.num_states = env.dim_observation_space
        self.num_actions = env.dim_action_space

        self.actor = Actor(self.num_states, self.hidden_size_a, self.num_actions)
        self.actor_target = Actor(self.num_states, self.hidden_size_c, self.num_actions)
        self.critic = Critic(self.num_states + self.num_actions, self.hidden_size_a, 1)
        self.critic_target = Critic(self.num_states + self.num_actions, self.hidden_size_c, 1)
        self.actor_optimizer  = optim.Adam(self.actor.parameters(), lr = self.lr_a)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr = self.lr_c)
        # update targets by setting same parameters with actors and critics
        self.soft_update(1.0)

        # create the replay buffer
        self.memory_size = int(1e6)
        self.memory = ReplayBuffer(self.memory_size)
        self.batch_size = 100


    def update_time(self, time):
        self.time_now = time

    def save_transition(self, transition):
        self.memory.store(transition)


    def soft_update(self,tao):

        for target_param, param in zip(self.actor_target.parameters(), self.actor.parameters()):
            target_param.data.copy_(param.data * tao + target_param.data * (1.0 - tao))

        for target_param, param in zip(self.critic_target.parameters(), self.critic.parameters()):
            target_param.data.copy_(param.data * tao + target_param.data * (1.0 - tao))


    def learn(self):

        if self.time_now >= self.train_stop_seconds:
            return

        states, actions, rewards, next_states, dones = self.memory.sample(min(self.batch_size, len(self.memory)))
        importances = 1

        states = torch.FloatTensor(states)
        actions = torch.FloatTensor(actions)
        rewards = torch.FloatTensor(rewards)
        next_states = torch.FloatTensor(next_states)
        dones = torch.FloatTensor(dones)
        noises = torch.FloatTensor(np.random.normal(0,self.noise_policy_intensity, rewards.shape))

        # Critic loss
        Qvals = self.critic.forward(states, actions)
        next_actions = self.actor_target.forward(next_states) + noises    # add the policy noise
        next_actions = torch.clamp(next_actions, -1, 1)
        next_Q = self.critic_target.forward(next_states, next_actions.detach())
        Qprime = rewards + self.gamma * next_Q *(1-dones)
        TD_errors = Qprime - Qvals
        weighted_TD_errors = TD_errors * importances
        critic_loss = nn.MSELoss()(weighted_TD_errors, torch.zeros(weighted_TD_errors.shape))
        # critic_loss = nn.MSELoss()(Qvals, Qprime)

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        self.update_count += 1
        if self.update_count % self.actor_update_fre == 0:

            self.update_count = 0

            # Actor loss
            policy_loss = -self.critic.forward(states, self.actor.forward(states)).mean()
            # update networks
            self.actor_optimizer.zero_grad()
            policy_loss.backward()
            self.actor_optimizer.step()

            # soft-update all targets
            self.soft_update(self.tao)


        TD_errors = TD_errors.detach().numpy().flatten()
        TD_errors_mse = np.linalg.norm(TD_errors)/TD_errors.shape[0] # this error cannot represent the performance of the learning

        return TD_errors_mse


    def get_action_noise(self):

        if self.time_now < self.train_stop_seconds:
            if self.noise_decay_mode == 'quadratic':
                x = self.time_now
                x1, y1 = 1, self.noise_intensity_max
                x2, y2 = self.train_stop_seconds/2, (self.noise_intensity_min + (self.noise_intensity_max - self.noise_intensity_min)/3)
                x3, y3 = self.train_stop_seconds, self.noise_intensity_min

                noise_intensity =  (x-x2)*(x-x3)/(x1-x2)/(x1-x3)*y1 + (x-x1)*(x-x3)/(x2-x1)/(x2-x3)*y2 + (x-x1)*(x-x2)/(x3-x1)/(x3-x2)*y3
                noise = np.random.normal(0,noise_intensity,1)

            if self.noise_decay_mode == 'linear':
                x = self.time_now
                x1, y1 = 1, self.noise_intensity_max
                x2, y2 = self.train_stop_seconds, self.noise_intensity_min

                noise_intensity = (x-x2)/(x1-x2)*(y1-y2)+y2
                noise = np.random.normal(0,noise_intensity,1)

            if self.noise_decay_mode == 'constant':
                noise_intensity = self.noise_intensity_max
                noise = np.random.normal(0,noise_intensity,1)
        else:
            noise = 0

        return noise


    def select_action(self, obs):


        action = self.actor(torch.from_numpy(obs).to(self.device, torch.float)).detach().cpu().numpy() \
              + self.get_action_noise()

        action = np.clip(action,-1,1)

        return action


    # used for evaluation
    def select_action_evl(self, obs, actor):

        action = actor(torch.from_numpy(obs).to(self.device, torch.float)).detach().cpu().numpy()

        return action







class ReplayBuffer:
    """
    This is the traditional replay buffer which does not adopt any techniques
    """

    def __init__(self, max_size):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)

    def store(self, transition):
        # transition = (state, action, reward, next_state, done)
        self.buffer.append(transition)

    def sample(self, batch_size):

        batch = random.sample(self.buffer, batch_size)
        batch = np.array(batch)

        state_batch = batch[:,0].tolist()
        action_batch = batch[:,1].tolist()
        reward_batch = batch[:,2].tolist()
        next_state_batch = batch[:,3].tolist()
        done_batch = batch[:,4].tolist()

        return state_batch, action_batch, reward_batch, next_state_batch, done_batch

    def __len__(self):
        return len(self.buffer)





class SumTree(object):
    """
    This SumTree code is a modified version and the original code is from:
    https://github.com/jaara/AI-blog/blob/master/SumTree.py
    Story data with its priority in the tree.
    """
    data_pointer = 0

    def __init__(self, capacity):
        self.capacity = capacity  # for all priority values
        self.tree = np.zeros(2 * capacity - 1)
        # [--------------Parent nodes-------------][-------leaves to recode priority-------]
        #             size: capacity - 1                       size: capacity
        self.data = np.zeros(capacity, dtype=object)  # for all transitions
        # [--------------data frame-------------]
        #             size: capacity

    def add(self, p, data):
        tree_idx = self.data_pointer + self.capacity - 1
        self.data[self.data_pointer] = data  # update data_frame
        self.update(tree_idx, p)  # update tree_frame

        self.data_pointer += 1
        if self.data_pointer >= self.capacity:  # replace when exceed the capacity
            self.data_pointer = 0

    def update(self, tree_idx, p):
        change = p - self.tree[tree_idx]
        self.tree[tree_idx] = p
        # then propagate the change through tree
        while tree_idx != 0:    # this method is faster than the recursive loop in the reference code
            tree_idx = (tree_idx - 1) // 2
            self.tree[tree_idx] += change

    def get_leaf(self, v):
        """
        Tree structure and array storage:
        Tree index:
             0         -> storing priority sum
            / \
          1     2
         / \   / \
        3   4 5   6    -> storing priority for transitions
        Array type for storing:
        [0,1,2,3,4,5,6]
        """
        parent_idx = 0
        while True:     # the while loop is faster than the method in the reference code
            cl_idx = 2 * parent_idx + 1         # this leaf's left and right kids
            cr_idx = cl_idx + 1
            if cl_idx >= len(self.tree):        # reach bottom, end search
                leaf_idx = parent_idx
                break
            else:       # downward search, always search for a higher priority node
                if v <= self.tree[cl_idx]:
                    parent_idx = cl_idx
                else:
                    v -= self.tree[cl_idx]
                    parent_idx = cr_idx

        data_idx = leaf_idx - self.capacity + 1
        return leaf_idx, data_idx, self.tree[leaf_idx], self.data[data_idx]

    @property
    def total_priority(self):
        return self.tree[0]  # the root


class SumTreeBuffer(object):

    """
    This is the a prioritized replay buffer which is based on SumTree
    """

    def __init__(self, capacity, scale = 0.7, total_steps = 30000):

        self.max_size = capacity
        self.offset = 0.01  # small amount to avoid zero priority
        self.a = scale  # [0~1] convert the importance of TD error to priority
        self.default_priority = 1.  # clipped abs error
        self.b = 1  #( 0.95^100 = 0.006)
        self.update_count = 0
        self.b_update_frequency = round(total_steps/2/100) # let b_scale decrease to 0 at the half of the total steps

        self.tree = SumTree(self.max_size)
        self.length = 0 # current length of the buffer

    def store(self, state, action, reward, next_state, done):
        transition = (state, action, reward, next_state, done)
        priority_ini = np.max(self.tree.tree[-self.tree.capacity:]) # set the max priority for new sample
        if priority_ini <= 0:
            priority_ini = self.default_priority
        self.tree.add(priority_ini, transition)
        self.length = min(self.length + 1, self.max_size)

    def sample(self, n):

        state_batch, action_batch, reward_batch, next_state_batch, done_batch = [], [], [], [], []
        tree_idx, data_idx = [], []
        prioritys = []
        priority_seg = self.tree.total_priority / n       # priority segment

        for i in range(n):
            a, b = priority_seg * i, priority_seg * (i + 1)
            v = np.random.uniform(a, b)
            t_idx, d_idx, priority, data = self.tree.get_leaf(v)
            if d_idx < self.length:
                state_batch.append(data[0])
                action_batch.append(data[1])
                reward_batch.append(data[2])
                next_state_batch.append(data[3])
                done_batch.append(data[4])
                tree_idx.append(t_idx)
                data_idx.append(d_idx)
                prioritys.append(priority)

        sample_probs = self.get_probabilities()

        _importance = self.get_importance(sample_probs[data_idx])
        _importance = _importance**(1 - self.b)
        importance_batch = [np.array([ele]) for ele in _importance]

        self.update_count += 1
        if self.update_count % self.b_update_frequency == 0:
            self.b = 0.95*self.b

        return state_batch, action_batch, reward_batch, next_state_batch, done_batch, importance_batch, tree_idx

    def get_probabilities(self):
        scaled_priorities = self.tree.tree[-self.tree.capacity : ] ** self.a
        sample_probabilities = scaled_priorities / sum(scaled_priorities)
        return sample_probabilities

    def get_importance(self, probabilities):
        importance = 1/self.length * 1/probabilities
        importance_normalized = importance / max(importance)
        return importance_normalized

    def priority_update(self, idx, errors):
        p_s = abs(errors) + self.offset
        for i, p in zip(idx, p_s):
            self.tree.update(i, p)





class PrioritizedReplayBuffer():
    """
    This is the a prioritized replay buffer which is not based on SumTree
    """

    def __init__(self, max_size):
        self.max_size = max_size
        self.buffer = deque(maxlen = max_size)
        self.priorities = deque(maxlen = max_size)

    def push(self, state, action, reward, next_state, done):
        experience = (state, action, reward, next_state, done)
        self.buffer.append(experience)
        self.priorities.append(max(self.priorities, default=1))

    def get_probabilities(self, priority_scale):
        scaled_priorities = np.array(self.priorities) ** priority_scale
        sample_probabilities = scaled_priorities / sum(scaled_priorities)
        return sample_probabilities

    def get_importance(self, probabilities):
        importance = 1/len(self.buffer) * 1/probabilities
        importance_normalized = importance / max(importance)
        return importance_normalized

    def sample(self, batch_size, priority_scale = 1.0):
        sample_size = min(len(self.buffer), batch_size)
        sample_probs = self.get_probabilities(priority_scale)
        sample_indices = random.choices(range(len(self.buffer)), k = sample_size, weights = sample_probs)
        batch = np.array(self.buffer)[sample_indices]

        state_batch = batch[:,0].tolist()
        action_batch = batch[:,1].tolist()
        reward_batch = batch[:,2].tolist()
        next_state_batch = batch[:,3].tolist()
        done_batch = batch[:,4].tolist()

        _importance = self.get_importance(sample_probs[sample_indices])
        importance = [np.array([ele]) for ele in _importance]

        return state_batch, action_batch, reward_batch, next_state_batch, done_batch, importance, sample_indices

    def set_priorities(self, indices, errors, offset = 0.1):
        for i,e in zip(indices, errors):
            self.priorities[i] = abs(e) + offset






class Critic(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(Critic, self).__init__()
        self.linear1 = nn.Linear(input_size, hidden_size)
        self.linear2 = nn.Linear(hidden_size, hidden_size)
        self.linear3 = nn.Linear(hidden_size, output_size)

    def forward(self, state, action):
        """
        Params state and actions are torch tensors
        """
        x = torch.cat([state, action], 1)
        x = F.relu(self.linear1(x))
        x = F.relu(self.linear2(x))
        x = self.linear3(x)

        return x

class Actor(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super(Actor, self).__init__()
        self.linear1 = nn.Linear(input_size, hidden_size)
        self.linear2 = nn.Linear(hidden_size, hidden_size)
        self.linear3 = nn.Linear(hidden_size, output_size)

    def forward(self, state):
        """
        Param state is a torch tensor
        """
        x = F.relu(self.linear1(state))
        x = F.relu(self.linear2(x))
        x = torch.tanh(self.linear3(x))

        return x

