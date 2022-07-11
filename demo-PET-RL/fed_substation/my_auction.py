# Copyright (C) 2017-2019 Battelle Memorial Institute
# file: simple_auction.py
"""Double-auction mechanism for the 5-minute markets in te30 and sgip1 examples

The substation_loop module manages one instance of this class per GridLAB-D substation.

Todo:
    * Initialize and update price history statistics
    * Allow for adjustment of clearing_scalar
    * Handle negative price bids from HVAC agents, currently they are discarded
    * Distribute marginal quantities and fractions; these are not currently applied to HVACs

"""
import math
import helics
import numpy as np
import my_tesp_support_api.helpers as helpers

# Class definition
class AUCTION:
    """This class implements a simplified version of the double-auction market embedded in GridLAB-D.

    References:
        `Market Module Overview - Auction <http://gridlab-d.shoutwiki.com/wiki/Market_Auction>`_

    Args:
        dict (dict): a row from the agent configuration JSON file
        key (str): the name of this agent, which is the market key from the agent configuration JSON file

    Attributes:
        name (str): the name of this auction, also the market key from the configuration JSON file
        std_dev (float): the historical standard deviation of the price, in $/kwh, from dict
        mean (float): the historical mean price in $/kwh, from dict
        period (float): the market clearing period in seconds, from dict
        pricecap (float): the maximum allowed market clearing price, in $/kwh, from dict
        max_capacity_reference_bid_quantity (float):
        statistic_mode (int): always 1, not used, from dict
        stat_mode (str): always ST_CURR, not used, from dict
        stat_interval (str): always 86400 seconds, for one day, not used, from dict
        stat_type (str): always mean and standard deviation, not used, from dict
        stat_value (str): always zero, not used, from dict
        curve_buyer (curve): data structure to accumulate buyer bids
        curve_seller (curve): data structure to accumulate seller bids
        refload (float): the latest substation load from GridLAB-D
        lmp (float): the latest locational marginal price from the bulk system market
        unresp (float): unresponsive load, i.e., total substation load less the bidding, running HVACs
        agg_unresp (float): aggregated unresponsive load, i.e., total substation load less the bidding, running HVACs
        agg_resp_max (float): total load of the bidding HVACs
        agg_deg (int): degree of the aggregate bid curve polynomial, should be 0 (zero or one bids), 1 (2 bids) or 2 (more bids)
        agg_c2 (float): second-order coefficient of the aggregate bid curve
        agg_c1 (float): first-order coefficient of the aggregate bid curve
        clearing_type (helpers.ClearingType): describes the solution type or boundary case for the latest market clearing
        clearing_quantity (float): quantity at the last market clearing
        clearing_price (float): price at the last market clearing
        marginal_quantity (float): quantity of a partially accepted bid
        marginal_frac (float): fraction of the bid quantity accepted from a marginal buyer or seller 
        clearing_scalar (float): used for interpolation at boundary cases, always 0.5
    """
    # ====================Define instance variables ===================================
    def __init__(self,dict,key):
        self.name = key
        self.std_dev = float(dict['init_stdev'])
        self.mean = float(dict['init_price'])
        self.period = float(dict['period'])
        # self.pricecap = float(dict['pricecap'])
        self.pricecap = 1.0
        self.max_capacity_reference_bid_quantity = float(dict['max_capacity_reference_bid_quantity'])
        self.statistic_mode = int(dict['statistic_mode'])
        self.stat_mode = dict['stat_mode']
        self.stat_interval = dict['stat_interval']
        self.stat_type = dict['stat_type']
        self.stat_value = dict['stat_value']

        # updated in collect_agent_bids, used in clear_market
        self.bids = []
        self.curve_buyer = None
        self.curve_seller = None

        self.refload = 0.0 # kVA
        self.refload_p = 0.0 # kV
        self.refload_q = 0.0 # kVar
        self.lmp = self.mean
        self.unresp = 0.0
        self.agg_unresp = 0.0
        self.agg_resp_max = 0.0
        self.agg_deg = 0
        self.agg_c2 = 0.0
        self.agg_c1 = 0.0
        self.clearing_type = helpers.ClearingType.NULL
        self.clearing_quantity = 0
        self.clearing_price = self.mean
        self.marginal_quantity = 0.0
        self.marginal_frac = 0.0

# added
        self.num_sellers = 0
        self.num_buyers = 0
        self.num_nontcp = 0
        self.market_condition = "double_auction"
        self.unresp_seller = 0.0 # this is for the extral power supply by the substation when too much load but few solars
        self.agg_unresp_seller = 0.0
        self.agg_resp_max_seller = 0.0
        self.agg_deg_seller = 0
        self.agg_c2_seller = 0.0
        self.agg_c1_seller = 0.0

        self.public_info = {}
        # 可以弄成和这个相关的，反正多余不够的确实就是从电网来走 self.max_capacity_reference_bid_quantity = float(dict['max_capacity_reference_bid_quantity'])
# added finished

        self.clearing_scalar = 0.5

        self.consumerSurplus = 0.0
        self.averageConsumerSurplus = 0.0
        self.supplierSurplus = 0.0
        self.unrespSupplierSurplus = 0.0

        self.bid_offset = 1e-4 # for numerical checks

        # publications and subscriptions
        self.subs = None
        self.pubs = None

    def get_helics_subspubs(self,input):
        self.subs = input[0]
        self.pubs = input[1]

    def get_refload (self):
        """Sets the refload attribute

        Args:
            kw (float): GridLAB-D substation load in kw
        """
        c = helics.helicsInputGetComplex (self.subs['subFeeder'])
        self.refload_p = c[0]*0.001
        self.refload_q = c[1]*0.001
        self.refload =  self.refload_p #math.sqrt(self.refload_p**2 + self.refload_q**2)
        # self.refload = 0.001 * helics.helicsInputGetDouble (self.subs['subFeeder']) # it is supposed to be complex, but double is also ok (unit: kVA)


    def get_lmp (self):
        """Sets the lmp attribute

        Args:
            lmp (float): locational marginal price from the bulk system market
        """
        self.lmp = helics.helicsInputGetDouble (self.subs['subLMP'])

                
    def initAuction (self):
        """Sets the clearing_price and lmp to the mean price
        """
        self.clearing_price = self.lmp = self.mean

    def update_statistics (self):
        """Update price history statistics - not implemented
        """
        sample_need = 0

    def clear_bids (self):
        """Re-initializes curve_buyer and curve_seller, sets the unresponsive load estimate to the total substation load.
        """
        self.curve_buyer = helpers.curve ()
        self.curve_seller = helpers.curve ()
        self.bids.clear()
        # self.unresp = self.refload
        self.unresp = 0 # modified by Yuanliang
        # added
        self.unresp_seller = self.max_capacity_reference_bid_quantity
        # added finishend

    def supplier_bid (self, bid):
        """Gather supplier bids into curve_seller

        Use this to enter curves in step-wise blocks.

        Args:
            bid ([float, float]): price in $/kwh, quantity in kW
        """
        price = bid[0]
        quantity = bid[1]
        self.curve_seller.add_to_curve (price, quantity, False)

    def collect_bid (self, bid):
        """Gather HVAC bids into curve_buyer

        Also adjusts the unresponsive load estimate, by subtracting the HVAC power
        if the HVAC is on.

        Args:
            bid ([float, float, Boolean]): price in $/kwh, quantity in kW and the HVAC on state
        """

        self.bids.append(bid) # receive bids
        price = bid[0]
        quantity = bid[1]
        hvac_needed = bid[2]
        role = bid[3]
        unresp_load = bid[4]
        base_covered = bid[6]

        if role == "seller":
            self.unresp_seller -= quantity
            if price > 0 and quantity > 0.0:
                self.curve_seller.add_to_curve (price, quantity, True)
        elif role == "buyer":
            if not base_covered:
                self.unresp += unresp_load # the calculation of unresponsive load may need be updated
            # it should collect the unresponsive load from houses, but also from other devices and loss
            if price > 0 and quantity > 0.0:
                self.curve_buyer.add_to_curve (price, quantity, hvac_needed)

        # if is_on:
        #     self.unresp -= quantity
        # if price > 0.0 and role == 'buyer':
        #     self.curve_buyer.add_to_curve (price, quantity, is_on)
        # if price > 0.0 and role == 'seller':
        #     self.curve_seller.add_to_curve (price, -1*quantity, is_on)


    def add_unresponsive_load(self, quantity):
        self.unresp += quantity

    def aggregate_bids(self):

        # for buyers
        #Aggregates the unresponsive load and responsive load bids for submission to the bulk system market
        if self.unresp > 0:
            self.curve_buyer.add_to_curve (self.pricecap, self.unresp, True)
        else:
            print ('$$ Unresp,BuyCount,BuyTotal,BuyOn,BuyOff', flush=True)
            print ('{:.3f}'.format(self.unresp),
                   self.curve_buyer.count, 
                   '{:.3f}'.format(self.curve_buyer.total), 
                   '{:.3f}'.format(self.curve_buyer.total_on), 
                   '{:.3f}'.format(self.curve_buyer.total_off), 
                   sep=',', flush=True)
        if self.curve_buyer.count > 0:
            self.curve_buyer.set_curve_order ('descending')
        self.agg_unresp, self.agg_resp_max, self.agg_deg, self.agg_c2, self.agg_c1 = helpers.aggregate_bid(self.curve_buyer)


        # for sellers
        # Aggregates the unresponsive load and responsive load bids for submission to the bulk system market # 这个处理的是buyer_curve那个向下的
        # 这个就相当于把unresponsive加进去，然后输出一个平滑的buyer_curve,然后还想把这个平滑的buyer_curve输出，但是没用到
        if self.unresp_seller > 0: # 把unresponsive弄入buyer_curve了
            self.curve_seller.add_to_curve (self.lmp, self.unresp_seller, True) # the substation price is lmp
        else: # 当unresp=<0,就是打印出一堆东西，对unresp的部分啥都不做
            print ('$$ Unresp_seller,SellCount,SellTotal,SellOn,SellOff', flush=True)
            print ('{:.3f}'.format(self.unresp_seller),
                   self.curve_buyer.count,
                   '{:.3f}'.format(self.curve_seller.total),
                   '{:.3f}'.format(self.curve_seller.total_on),
                   '{:.3f}'.format(self.curve_seller.total_off),
                   sep=',', flush=True)
        if self.curve_seller.count > 0:
            self.curve_seller.set_curve_order ('ascending')
        self.agg_unres_seller, self.agg_resp_max_seller, self.agg_deg_seller, self.agg_c2_seller, self.agg_c1_seller = helpers.aggregate_bid(self.curve_seller)
        # 这个只是弄了个curve_buyer的线，并没有对curve_buyer做什么


        # analyze the market condition
        self.num_sellers = self.num_buyers = self.num_nontcp = 0
        for bid in self.bids:
            if bid[3] == 'buyer':
                self.num_buyers += 1
            elif bid[3] == 'seller':
                self.num_sellers += 1
            else:
                self.num_nontcp += 1
        if  self.num_buyers == 0 and self.num_sellers != 0:
            self.market_condition = "flexible-generation"
        elif self.num_sellers == 0 and self.num_buyers != 0:
            self.market_condition = "flexible-load"
        else:
            self.market_condition = "double-auction"



    def publish_agg_bids_for_buyer(self):
        helics.helicsPublicationPublishDouble (self.pubs['pubUnresp'], self.agg_unresp)
        helics.helicsPublicationPublishDouble (self.pubs['pubMax'], self.agg_resp_max)
        helics.helicsPublicationPublishDouble (self.pubs['pubC2'], self.agg_c2)
        helics.helicsPublicationPublishDouble (self.pubs['pubC1'], self.agg_c1)
        helics.helicsPublicationPublishInteger (self.pubs['pubDeg'], self.agg_deg)

    def publish_clearing_price(self):
        helics.helicsPublicationPublishDouble (self.pubs['pubAucPrice'], self.clearing_price)

    def clear_market (self, tnext_clear=0, time_granted=0):
        """Solves for the market clearing price and quantity

        Uses the current contents of curve_seller and curve_buyer.
        Updates clearing_price, clearing_quantity, clearing_type,
        marginal_quantity and marginal_frac.

        Args:
            tnext_clear (int): next clearing time in FNCS seconds, should be <= time_granted, for the log file only
            time_granted (int): the current time in FNCS seconds, for the log file only
        """
        # if self.max_capacity_reference_bid_quantity > 0:
        #     self.curve_seller.add_to_curve (self.lmp, self.max_capacity_reference_bid_quantity, True)
        # if self.curve_seller.count > 0:
        #     self.curve_seller.set_curve_order ('ascending')

        self.unresponsive_sell = self.responsive_sell = self.unresponsive_buy = self.responsive_buy = 0

        ## add
        # if self.curve_buyer.count == 1 and self.curve_seller.count == 1:
        #     self.clearing_price = float(self.curve_buyer.price[0])
        #     self.clearing_quantity = int(self.curve_buyer.quantity[0])
        #     self.clearing_type = helpers.ClearingType.NULL #"ClearingType.NULL"
        #     #print(f"##,{tnext_clear},{tnext_clear},{self.clearing_type},{self.clearing_quantity},{self.clearing_price},{self.curve_buyer.count},{self.unresp},0,{self.curve_seller.count},{self.unresp_seller},0,0.000,0.000000,0,0,0.0000,0.0000,0.0000,0.0000")
        #     return
        ## add finish

        if self.curve_buyer.count > 0 and self.curve_seller.count > 0:
            a = self.pricecap
            b = -self.pricecap
            check = 0
            demand_quantity = supply_quantity = 0
            for i in range(self.curve_seller.count):
                if self.curve_seller.price[i] == self.pricecap:
                    self.unresponsive_sell += self.curve_seller.quantity[i]
                else:
                    self.responsive_sell += self.curve_seller.quantity[i]
            for i in range(self.curve_buyer.count):
                if self.curve_buyer.price[i] == self.pricecap:
                    self.unresponsive_buy += self.curve_buyer.quantity[i]
                else:
                    self.responsive_buy += self.curve_buyer.quantity[i]
            # Calculate clearing quantity and price here
            # Define the section number of the buyer and the seller curves respectively as i and j
            i = j = 0
            self.clearing_type = helpers.ClearingType.NULL
            self.clearing_quantity = self.clearing_price = 0
            while i < self.curve_buyer.count and j < self.curve_seller.count and self.curve_buyer.price[i] >= self.curve_seller.price[j]:
                buy_quantity = demand_quantity + self.curve_buyer.quantity[i]
                sell_quantity = supply_quantity + self.curve_seller.quantity[j]
                # If marginal buyer currently:
                if buy_quantity > sell_quantity:
                    self.clearing_quantity = supply_quantity = sell_quantity
                    a = b = self.curve_buyer.price[i]
                    j += 1
                    check = 0
                    self.clearing_type = helpers.ClearingType.BUYER
                # If marginal seller currently:
                elif buy_quantity < sell_quantity:
                    self.clearing_quantity = demand_quantity = buy_quantity
                    a = b = self.curve_seller.price[j]
                    i += 1
                    check = 0
                    self.clearing_type = helpers.ClearingType.SELLER
                # Buy quantity equal sell quantity but price split  
                else:
                    self.clearing_quantity = demand_quantity = supply_quantity = buy_quantity
                    a = self.curve_buyer.price[i]
                    b = self.curve_seller.price[j]
                    i += 1
                    j += 1
                    check = 1
            # End of the curve comparison, and if EXACT, get the clear price
            if a == b:
                self.clearing_price = a 
            # If there was price agreement or quantity disagreement
            if check:
                self.clearing_price = a 
                if supply_quantity == demand_quantity:
                    # At least one side exhausted at same quantity
                    if i == self.curve_buyer.count or j == self.curve_seller.count:
                        if a == b:
                            self.clearing_type = helpers.ClearingType.EXACT
                        else:
                            self.clearing_type = helpers.ClearingType.PRICE
                    # Exhausted buyers, sellers unsatisfied at same price
                    elif i == self.curve_buyer.count and b == self.curve_seller.price[j]:
                        self.clearing_type = helpers.ClearingType.SELLER
                    # Exhausted sellers, buyers unsatisfied at same price
                    elif j == self.curve_seller.count and a == self.curve_buyer.price[i]:
                        self.clearing_type = helpers.ClearingType.BUYER
                    # Both sides satisfied at price, but one side exhausted  
                    else:
                        if a == b:
                            self.clearing_type = helpers.ClearingType.EXACT
                        else:
                            self.clearing_type = helpers.ClearingType.PRICE
                # No side exausted
                else:
                    # Price changed in both directions
                    if a != self.curve_buyer.price[i] and b != self.curve_seller.price[j] and a == b:
                        self.clearing_type = helpers.ClearingType.EXACT
                    # Sell price increased ~ marginal buyer since all sellers satisfied
                    elif a == self.curve_buyer.price[i] and b != self.curve_seller.price[j]:
                        self.clearing_type = helpers.ClearingType.BUYER
                    # Buy price increased ~ marginal seller since all buyers satisfied
                    elif a != self.curve_buyer.price[i] and b == self.curve_seller.price[j]:
                        self.clearing_type = helpers.ClearingType.SELLER
                        self.clearing_price = b # use seller's price, not buyer's price
                    # Possible when a == b, q_buy == q_sell, and either the buyers or sellers are exhausted
                    elif a == self.curve_buyer.price[i] and b == self.curve_seller.price[j]:
                        if i == self.curve_buyer.count and j == self.curve_seller.count:
                            self.clearing_type = helpers.ClearingType.EXACT
                        elif i == self.curve_buyer.count:
                            self.clearing_type = helpers.ClearingType.SELLER
                        elif j == self.curve_seller.count:
                            self.clearing_type = helpers.ClearingType.BUYER
                    else:
                        # Marginal price
                        self.clearing_type = helpers.ClearingType.PRICE
                
                # If ClearingType.PRICE, calculate the clearing price here
                dHigh = dLow = 0
                if self.clearing_type == helpers.ClearingType.PRICE:
                    avg = (a+b)/2.0
                    # Calculating clearing price limits:   
                    dHigh = a if i == self.curve_buyer.count else self.curve_buyer.price[i]
                    dLow = b if j == self.curve_seller.count else self.curve_seller.price[j]
                    # Needs to be just off such that it does not trigger any other bids
                    if a == self.pricecap and b != -self.pricecap:
                        if self.curve_buyer.price[i] > b:
                            self.clearing_price = self.curve_buyer.price[i] + self.bid_offset
                        else:
                            self.clearing_price = b 
                    elif a != self.pricecap and b == -self.pricecap:
                        if self.curve_seller.price[j] < a:
                            self.clearing_price = self.curve_seller.price[j] - self.bid_offset
                        else:
                            self.clearing_price = a 
                    elif a == self.pricecap and b == -self.pricecap:
                        if i == self.curve_buyer.count and j == self.curve_seller.count:
                            self.clearing_price = 0 # no additional bids on either side
                        elif j == self.curve_seller.count: # buyers left
                            self.clearing_price = self.curve_buyer.price[i] + self.bid_offset
                        elif i == self.curve_buyer.count: # sellers left
                            self.clearing_price = self.curve_seller.price[j] - self.bid_offset
                        else: # additional bids on both sides, just no clearing
                            self.clearing_price = (dHigh + dLow)/2
                    else:
                        if i != self.curve_buyer.count and self.curve_buyer.price[i] == a:
                            self.clearing_price = a 
                        elif j != self.curve_seller.count and self.curve_seller.price[j] == b:
                            self.clearing_price = b 
                        elif i != self.curve_buyer.count and avg < self.curve_buyer.price[i]:
                            self.clearing_price = dHigh + self.bid_offset
                        elif j != self.curve_seller.count and avg > self.curve_seller.price[j]:
                            self.clearing_price = dLow - self.bid_offset
                        else:
                            self.clearing_price = avg 
                                
            # Check for zero demand but non-zero first unit sell price
            if self.clearing_quantity == 0:
                self.clearing_type = helpers.ClearingType.NULL
                if self.curve_seller.count > 0 and self.curve_buyer.count == 0:
                    self.clearing_price = self.curve_seller.price[0] - self.bid_offset
                elif self.curve_seller.count == 0 and self.curve_buyer.count > 0:
                    self.clearing_price = self.curve_buyer.price[0] + self.bid_offset
                else:
                    if self.curve_seller.price[0] == self.pricecap:
                        self.clearing_price = self.curve_buyer.price[0] + self.bid_offset
                    elif self.curve_seller.price[0] == -self.pricecap:
                        self.clearing_price = self.curve_seller.price[0] - self.bid_offset  
                    else:
                        self.clearing_price = self.curve_seller.price[0] + (self.curve_buyer.price[0] - self.curve_seller.price[0]) * self.clearing_scalar
           
            elif self.clearing_quantity < self.unresponsive_buy:
                self.clearing_type = helpers.ClearingType.FAILURE
                self.clearing_price = self.pricecap
            
            elif self.clearing_quantity < self.unresponsive_sell:
                self.clearing_type = helpers.ClearingType.FAILURE
                self.clearing_price = -self.pricecap
            
            elif self.clearing_quantity == self.unresponsive_buy and self.clearing_quantity == self.unresponsive_sell:
                # only cleared unresponsive loads
                self.clearing_type = helpers.ClearingType.PRICE
                self.clearing_price = 0.0
            
        # If the market mode MD_NONE and at least one side is not given
        else:
            if self.curve_seller.count > 0 and self.curve_buyer.count == 0:
                self.clearing_price = self.curve_seller.price[0] - self.bid_offset
            elif self.curve_seller.count == 0 and self.curve_buyer.count > 0: # in TE-30 example
                self.clearing_price = self.curve_buyer.price[0] + self.bid_offset
            elif self.curve_seller.count > 0 and self.curve_buyer.count > 0:
                self.clearing_price = self.curve_seller.price[0] + (self.curve_buyer.price[0] - self.curve_seller.price[0]) * self.clearing_scalar
            elif self.curve_seller.count == 0 and self.curve_buyer.count == 0:
                self.clearing_price = 0.0
            self.clearing_quantity = 0
            self.clearing_type = helpers.ClearingType.NULL
            if self.curve_seller.count == 0 :
                missingBidder = "seller"
            elif self.curve_buyer.count == 0:
                missingBidder = "buyer"
            print ('  Market %s fails to clear due to missing %s' % (self.name, missingBidder), flush=True)
            
        # Calculation of the marginal 
        marginal_total = self.marginal_quantity = self.marginal_frac = 0.0
        if self.clearing_type == helpers.ClearingType.BUYER:
            marginal_subtotal = 0
            i = 0
            for i in range(self.curve_buyer.count):
                if self.curve_buyer.price[i] > self.clearing_price:
                    marginal_subtotal = marginal_subtotal + self.curve_buyer.quantity[i]
                else:
                    break
            self.marginal_quantity =  self.clearing_quantity - marginal_subtotal
            for j in range(i, self.curve_buyer.count):
                if self.curve_buyer.price[i] == self.clearing_price:
                    marginal_total += self.curve_buyer.quantity[i]
                else:
                    break
            if marginal_total > 0.0:
                self.marginal_frac = float(self.marginal_quantity) / marginal_total
       
        elif self.clearing_type == helpers.ClearingType.SELLER:
            marginal_subtotal = 0
            i = 0
            for i in range(0, self.curve_seller.count):
                if self.curve_seller.price[i] > self.clearing_price:
                    marginal_subtotal = marginal_subtotal + self.curve_seller.quantity[i]
                else:
                    break
            self.marginal_quantity =  self.clearing_quantity - marginal_subtotal
            for j in range(i, self.curve_seller.count):
                if self.curve_seller.price[i] == self.clearing_price:
                    marginal_total += self.curve_seller.quantity[i]
                else:
                    break
            if marginal_total > 0.0:
                self.marginal_frac = float (self.marginal_quantity) / marginal_total 
        
        else:
            self.marginal_quantity = 0.0
            self.marginal_frac = 0.0
        # print ('##', time_granted, tnext_clear, self.clearing_type, self.clearing_quantity, 
        #        self.clearing_price,
        #        self.curve_buyer.count, self.unresponsive_buy, self.responsive_buy,
        #        self.curve_seller.count, self.unresponsive_sell, self.responsive_sell,
        #        self.marginal_quantity, self.marginal_frac, self.lmp, self.refload,
        #        self.consumerSurplus, self.averageConsumerSurplus, self.supplierSurplus,
        #        self.unrespSupplierSurplus, sep=',', flush=True)

    def surplusCalculation(self, tnext_clear=0, time_granted=0):
        """Calculates consumer surplus (and its average) and supplier surplus.

        This function goes through all the bids higher than clearing price from buyers to calculate consumer surplus,
         and also accumlates the quantities that will be cleared while doing so. Of the cleared quantities,
         the quantity for unresponsive loads are also collected.
         Then go through each seller to calculate supplier surplus.
         Part of the supplier surplus corresponds to unresponsive load are excluded and calculated separately.

        :param tnext_clear (int): next clearing time in FNCS seconds, should be <= time_granted, for the log file only
        :param time_granted (int): the current time in FNCS seconds, for the log file only
        :return: None
        """
        numberOfUnrespBuyerAboveClearingPrice = 0
        numberOfResponsiveBuyerAboveClearingPrice = 0
        self.supplierSurplus = 0.0
        self.averageConsumerSurplus = 0.0
        self.consumerSurplus = 0.0
        self.unrespSupplierSurplus = 0.0
        grantedRespQuantity = 0.0
        grantedUnrespQuantity = 0.0
        declinedQuantity = 0.0
        # assuming the buyers are ordered descending by price
        for i in range(self.curve_buyer.count):
            # if a buyer pays higher than clearing_price, the power is granted
            if self.curve_buyer.price[i] >= self.clearing_price:
                # unresponsive load, they pay infinite amount price, here it is set at self.pricecap
                if self.curve_buyer.price[i] == self.pricecap:
                    grantedUnrespQuantity += self.curve_buyer.quantity[i]
                    numberOfUnrespBuyerAboveClearingPrice += 1
                # responsive load, this is the part consumer surplus is calculated
                else:
                    grantedRespQuantity += self.curve_buyer.quantity[i]
                    numberOfResponsiveBuyerAboveClearingPrice += 1
                    self.consumerSurplus += (self.curve_buyer.price[i] - self.clearing_price) * self.curve_buyer.quantity[i]
            # if a buy pays lower than clearing_price, it does not get the quantity requested
            else:
                declinedQuantity += self.curve_buyer.quantity[i]
        if numberOfResponsiveBuyerAboveClearingPrice != 0:
            self.averageConsumerSurplus = self.consumerSurplus / numberOfResponsiveBuyerAboveClearingPrice
        # assuming the sellers are ordered ascending by their price
        for i in range(self.curve_seller.count):
            # if a seller has a wholesale price/base price lower than clearing_price, their power is used
            if self.curve_seller.price[i] <= self.clearing_price:
                # satisfy quantity requested by unresponsive load first since they pay infinite price
                # when the unresponsive load use up all power from the supplier
                if grantedUnrespQuantity >= self.curve_seller.quantity[i]:
                    self.unrespSupplierSurplus += (self.clearing_price - self.curve_seller.price[i]) * self.curve_seller.quantity[i]
                    grantedUnrespQuantity -= self.curve_seller.quantity[i]
                # when the unresponsive load use part of the power from the supplier
                elif grantedUnrespQuantity != 0.0:
                    self.unrespSupplierSurplus += (self.clearing_price - self.curve_seller.price[i]) * grantedUnrespQuantity
                    leftOverQuantityFromSeller = self.curve_seller.quantity[i] - grantedUnrespQuantity
                    grantedUnrespQuantity = 0.0
                    # leftover quantity from this supplier will be used by responsive load
                    # when leftover quantity is used up by the responsive load
                    if grantedRespQuantity >= leftOverQuantityFromSeller:
                        self.supplierSurplus += (self.clearing_price - self.curve_seller.price[i]) * leftOverQuantityFromSeller
                        grantedRespQuantity -= leftOverQuantityFromSeller
                    # when leftover quantity satisfies all the quantity the responsive load asked
                    else:
                        self.supplierSurplus += (self.clearing_price - self.curve_seller.price[i]) * grantedRespQuantity
                        grantedRespQuantity = 0.0
                        break
                # if the quantity requested by unresponsive load are satisfied, responsive load requests are considered
                # when supplier quantity is used up by the responsive load
                elif grantedRespQuantity >= self.curve_seller.quantity[i]:
                    self.supplierSurplus += (self.clearing_price - self.curve_seller.price[i]) * self.curve_seller.quantity[i]
                    grantedRespQuantity -= self.curve_seller.quantity[i]
                # when supplier quantity satisfies all the quantity the responsive load requested
                else:
                    self.supplierSurplus += (self.clearing_price - self.curve_seller.price[i]) * grantedRespQuantity
                    grantedRespQuantity = 0.0
                    break
        if grantedRespQuantity != 0.0:
            print('cleared {:.4f} more quantity than supplied.'.format(grantedRespQuantity))
        print ('##', 
               time_granted, 
               tnext_clear, 
               self.clearing_type, 
               '{:.3f}'.format(self.clearing_quantity), 
               '{:.6f}'.format(self.clearing_price),
               self.curve_buyer.count, 
               '{:.3f}'.format(self.unresponsive_buy), 
               '{:.3f}'.format(self.responsive_buy),
               self.curve_seller.count, 
               '{:.3f}'.format(self.unresponsive_sell), 
               '{:.3f}'.format(self.responsive_sell),
               '{:.3f}'.format(self.marginal_quantity), 
               '{:.6f}'.format(self.marginal_frac), 
               '{:.6f}'.format(self.lmp), 
               '{:.3f}'.format(self.refload),
               '{:.4f}'.format(self.consumerSurplus), 
               '{:.4f}'.format(self.averageConsumerSurplus), 
               '{:.4f}'.format(self.supplierSurplus),
               '{:.4f}'.format(self.unrespSupplierSurplus), 
               sep=',', flush=True)

    def publish_cleared_market_information(self):

        self.public_info = {}

        helics.helicsPublicationPublishDouble (self.pubs['pubAucPrice'], self.clearing_price)

        if len(self.bids)>0:
            self.public_info['ratio-seller'] = self.num_sellers/len(self.bids)
            self.public_info['ratio-buyer'] = self.num_buyers/len(self.bids)
        else:
            self.public_info['ratio-seller'] = 0
            self.public_info['ratio-buyer'] = 0

        seller_quantity_total = 0
        buyer_quantity_total = 0
        seller_price_list = []
        buyer_price_list = []
        for bid in self.bids:
            price = bid[0]
            quantity = bid[1]
            hvac_needed = bid[2]
            role = bid[3]
            unresp_load = bid[4]
            base_covered = bid[6]

            if role == 'seller':
                seller_quantity_total += quantity
                if price > 0:
                    seller_price_list.append(price)

            if role == 'buyer':
                buyer_quantity_total += quantity
                if not base_covered:
                    buyer_quantity_total += unresp_load
                if price > 0:
                    buyer_price_list.append(price)

        self.public_info['seller-quantity-total'] = seller_quantity_total
        self.public_info['buyer-quantity-total'] = buyer_quantity_total

        if len(seller_price_list)>0:
            self.public_info['mean-price-seller'] = np.mean(seller_price_list)
            self.public_info['std-price-seller'] = np.std(seller_price_list)
        else:
            self.public_info['mean-price-seller'] = 0
            self.public_info['std-price-seller'] = 0
        if len(buyer_price_list)>0:
            self.public_info['mean-price-buyer'] = np.mean(buyer_price_list)
            self.public_info['std-price-buyer'] = np.std(buyer_price_list)
        else:
            self.public_info['mean-price-buyer'] = 0
            self.public_info['std-price-buyer'] = 0

        self.public_info['cleared-price'] = self.clearing_price
        self.public_info['cleared-quantity'] = self.clearing_quantity
        self.public_info['LMP'] = self.lmp

        return self.public_info
