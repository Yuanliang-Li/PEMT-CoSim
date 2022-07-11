import numpy as np
from collections import deque

class BIDING_ENV:

    def __init__(self, num_prosumers, name, price_cap, duration, mode):

        self.num_prosumers = num_prosumers
        self.name = name # prosumer name
        self.price_cap = price_cap
        self.duration_seconds = duration # unit: second
        self.time_now = 0
        self.has_seller_agent = False
        self.has_buyer_agent = False
        if mode == "seller-buyer" or mode == "seller-only":
            self.has_seller_agent = True
        if mode == "seller-buyer" or mode == "buyer-only":
            self.has_buyer_agent = True


        self.obs_high = [
            1,    # seller ratio
            1,    # buyer ratio
            10*self.num_prosumers,  # seller total quantity of last auction (kw)
            10*self.num_prosumers,  # buyer total quantity of last auction
            1,    # mean of all sellers' bidding price of last auction
            1,    # standard deviation of all sellers bidding price
            1,    # mean of all buyers' bidding price of last auction
            1,    # standard deviation of all buyers' bidding price
            1,    # cleared price of last auction
            10*self.num_prosumers,  # cleared quantity of last auction
            1,    # current LMP
            20,   # current available generation capacity (PV + battery, kw)
            15,   # current load consumption (kw)
            ]
        self.obs_low = [
            0,    # seller ratio
            0,    # buyer ratio
            0,    # seller total quantity of last auction (kw)
            0,    # buyer total quantity of last auction
            0,    # mean of all sellers' bidding price of last auction
            0,    # standard deviation of all sellers bidding price
            0,    # mean of all buyers' bidding price of last auction
            0,    # standard deviation of all buyers' bidding price
            0,    # cleared price of last auction
            0,   # cleared quantity of last auction
            0,   # current LMP
            0,   # current available generation capacity (PV + battery, kw)
            0,   # current load consumption (kw)
            ]


        self.dim_action_space = 1
        self.dim_observation_space = len(self.obs_high)

        self.obs = []


        self.transition_seller = []  # state, action, reward, next_state, done
        self.transition_buyer = []  # state, action, reward, next_state, done
        self.current_transition = {'state': [],
                                   'action': -10,
                                   'rl-role': 'rl-ntcp',
                                   'reward': 0,
                                   'next-state': [],
                                   'done':False} # state, action, reward, next_state, done

    def update_time(self, time):
        self.time_now = time


    def actionToPrice(self, action):

        x = action[0]
        x1, y1 = -1, 0
        x2, y2 = 0, 0.1
        x3, y3 = 1, 0.6

        # 二次函数三点法
        price = (x-x2)*(x-x3)/(x1-x2)/(x1-x3)*y1 + \
                (x-x1)*(x-x3)/(x2-x1)/(x2-x3)*y2 + \
                (x-x1)*(x-x2)/(x3-x1)/(x3-x2)*y3


        price = max(price, 0)
        price = min(price, self.price_cap)

        return price


    def getInitialObservation(self, self_info):
        obs = [
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            self_info['power-generation'],
            self_info['load-consumption']
        ]

        self.obs = np.array(obs)/np.array(self.obs_high)

        return self.obs



    def getObservation(self, auction_info, self_info):

        if not auction_info:
            obs = [
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                self_info['power-generation'],
                self_info['load-consumption']]
        else:
            obs = [
                auction_info['ratio-seller'],
                auction_info['ratio-buyer'],
                auction_info['seller-quantity-total'],
                auction_info['buyer-quantity-total'],
                auction_info['mean-price-seller'],
                auction_info['std-price-seller'],
                auction_info['mean-price-buyer'],
                auction_info['std-price-buyer'],
                auction_info['cleared-price'],
                auction_info['cleared-quantity'],
                auction_info['LMP'],
                self_info['power-generation'],
                self_info['load-consumption']]

        self.obs = np.array(obs)/np.array(self.obs_high)

        self.update_transition('observation',self.obs)

        return self.obs



    def get_reward(self, bid, cleared_price):

        # [bid_price, quantity, hvac.power_needed, role, unres_kw, name]
        bid_price = bid[0]
        bid_quantity = bid[1]
        role = bid[3]


        if bid_quantity <= 0 or role == 'none-participant':
            reward = 0
            return reward


        if role == 'seller':
            if bid_price <= cleared_price:
                reward = bid_quantity*(cleared_price - 0.05)
            else:
                reward = -bid_quantity*0.05

        if role == 'buyer':
            if bid_price >= cleared_price:
                reward = 1
            else:
                reward = -1

        self.update_transition('reward', reward)

        return reward



    def update_transition(self, key, value, rl_role = 'rl-ntcp'):

        if key == 'observation':
            if len(self.current_transition['state']) == 0:
                self.current_transition['state'] = value
            else:
                self.current_transition['next-state'] = value
                if self.current_transition['rl-role'] == 'rl-seller':
                    self.transition_seller.clear()
                    self.transition_seller.append(self.current_transition['state'])
                    self.transition_seller.append(self.current_transition['action'])
                    self.transition_seller.append(np.array([self.current_transition['reward']]))
                    self.transition_seller.append(self.current_transition['next-state'])
                    self.transition_seller.append(np.array([self.current_transition['done']]))
                if self.current_transition['rl-role'] == 'rl-buyer':
                    self.transition_buyer.clear()
                    self.transition_buyer.append(self.current_transition['state'])
                    self.transition_buyer.append(self.current_transition['action'])
                    self.transition_buyer.append(np.array([self.current_transition['reward']]))
                    self.transition_buyer.append(self.current_transition['next-state'])
                    self.transition_buyer.append(np.array([self.current_transition['done']]))
                self.current_transition['state'] = value

        if key == 'action':
            self.current_transition['action'] = value
            self.current_transition['rl-role'] = rl_role

        if key == 'reward':
            self.current_transition['reward'] = value
