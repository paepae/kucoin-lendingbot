from decimal import Decimal
from time import sleep

import utils
from .base import BaseBot


class StepBot(BaseBot):

    def execute(self, should_execute: bool) -> None:
        account_balance = self.get_account_balance()
        total_balance = account_balance["Balance"]
        available_balance = account_balance["Available"]

        if total_balance <= 0:
            self.log("TotalBalance=[0]")
            return

        my_active_open_orders = self.get_my_active_open_orders()
        my_order_interest_daily_rate = None
        pending_balance = Decimal(0)

        for open_order in my_active_open_orders:
            my_order_interest_daily_rate = open_order["DailyInterestRate"]
            my_order_size = open_order["Size"]
            my_pending_size = my_order_size - open_order["FilledSize"]
            pending_balance += my_pending_size
            self.log(f"Active open order: DailyInterestRate=[{my_order_interest_daily_rate}%] Size=[{my_order_size}] PendingSize=[{my_pending_size}]")

        balance_lent = total_balance - available_balance - pending_balance
        balance_utilization_rate = Decimal(utils.round_down_to_decimal_places_string(balance_lent / total_balance * 100, 2))
        self.log(f"TotalBalance=[{total_balance}] AvailableBalance=[{available_balance}] PendingBalance=[{pending_balance}] UtilizationRate=[{balance_utilization_rate}%] ActualAccruedInterest=[{account_balance['ActualAccruedInterest']}]")

        current_daily_interest_rate = account_balance["AverageDailyInterestRate"]
        effective_daily_interest_rate_on_total_balance = account_balance["EffectiveDailyInterestRateOnTotalBalance"]
        effective_yearly_interest_rate_on_total_balance = effective_daily_interest_rate_on_total_balance * 365
        expected_daily_usdt = effective_daily_interest_rate_on_total_balance * total_balance / 100
        expected_hourly_usdt = expected_daily_usdt / 24
        self.log(f"AverageDailyInterestRate=[{utils.round_down_to_decimal_places_string(current_daily_interest_rate, 3)}%]")
        self.log(f"EffectiveDailyInterestRateOnTotalBalance=[{utils.round_down_to_decimal_places_string(effective_daily_interest_rate_on_total_balance, 3)}%] EffectiveYearlyInterestRateOnTotalBalance=[{utils.round_down_to_decimal_places_string(effective_yearly_interest_rate_on_total_balance, 3)}%]")
        self.log(f"Expected HourlyInterest=[{utils.round_down_to_decimal_places_string(expected_hourly_usdt, self.config.currency_earning_report_decimal_places)}] DailyInterest=[{utils.round_down_to_decimal_places_string(expected_daily_usdt, self.config.currency_earning_report_decimal_places)}]")

        min_daily_interest_rate = self.calculate_minimum_daily_interest_rate(balance_utilization_rate)
        market_data = self.get_market_data(my_active_open_orders, min_daily_interest_rate)
        my_optimal_rate = self.calculate_my_optimal_daily_interest_rate(market_data, my_active_open_orders, min_daily_interest_rate)
        self.log(f"LowestRate=[{market_data['LowestRate']}%] BigPlayerRate=[{market_data['BigPlayerRate']}%] MyOptimalRate=[{my_optimal_rate}%]")

        if not should_execute:
            return

        canceled_size = Decimal(0)

        if len(my_active_open_orders) > 1:
            self.log(f"Keep my open orders")
            return
        elif len(my_active_open_orders) == 1:
            my_active_open_order = my_active_open_orders[0]
            my_daily_interest_rate = my_active_open_order["DailyInterestRate"]
            if my_daily_interest_rate > my_optimal_rate:
                try:
                    self.margin_client.cancel_lend_order(my_active_open_order["OrderId"])
                    canceled_size = my_active_open_order["Size"] - my_active_open_order["FilledSize"]
                    available_balance += canceled_size
                    self.log(f"Canceled open order: DailyInterestRate=[{my_daily_interest_rate}%] CanceledSize=[{canceled_size}] NewAvailableBalance=[{available_balance}]")
                except Exception as ex:
                    self.log(f"Failed to cancel lend order: Error:[{repr(ex)}]")
                    return
            else:
                effective_daily_interest_rate = self.calculate_effective_daily_interest_rate(my_daily_interest_rate)
                effective_yeary_interest_rate = effective_daily_interest_rate * 365
                self.log(f"Keep my open order: DailyInterestRate=[{my_daily_interest_rate}%] EffectiveDailyInterestRate=[{utils.round_down_to_decimal_places_string(effective_daily_interest_rate, 3)}%] EffectiveYearlyInterestRate=[{utils.round_down_to_decimal_places_string(effective_yeary_interest_rate, 3)}%]")
                return

        lending_size = self.calculate_lending_size(total_balance, available_balance)

        if lending_size == Decimal(0):
            self.log("Not enough available balance")
            return

        if (available_balance - canceled_size) < lending_size:
            # Wait for canceled size to be released
            sleep(1)

        if my_optimal_rate >= self.config.step_bot.term_28_daily_interest_rate:
            term = 28
        elif my_optimal_rate >= self.config.step_bot.term_14_daily_interest_rate:
            term = 14
        else:
            term = 7

        self.create_lend_order(my_optimal_rate, lending_size, term)

        return


    def get_market_data(self, my_active_open_orders: list, min_daily_interest_rate: Decimal) -> dict:
        market_data_response = self.get_lending_market_data()

        big_player_size_threshold = self.config.step_bot.big_player_size_threshold

        lowest_rate = Decimal(market_data_response[0]["dailyIntRate"]) * 100
        big_player_rate = Decimal(0)
        size = Decimal(0)

        my_orders_by_rate = {order["DailyInterestRate"]: order for order in my_active_open_orders}

        offer_list = list()
        for line in market_data_response:
            line_rate = Decimal(line["dailyIntRate"]) * Decimal(100)
            if line_rate < min_daily_interest_rate:
                continue

            line_rate = Decimal(utils.round_down_to_decimal_places_string(line_rate, 3))
            line_size = Decimal(line["size"])

            if line_rate > big_player_rate:
                offer_list.append({
                    "Rate": line_rate,
                    "Size": line_size,
                })

                big_player_rate = line_rate
                size = line_size

                my_open_order = my_orders_by_rate.get(line_rate)
                if my_open_order is not None:
                    my_size = my_open_order["Size"] - my_open_order["FilledSize"]
                    size -= my_size
            else:
                size += line_size

            if size > big_player_size_threshold:
                break

        if big_player_rate == 0:
            raise Exception("BigPlayerRate is zero. Something seems to be wrong.")

        result = {
            "LowestRate": Decimal(utils.round_down_to_decimal_places_string(lowest_rate, 3)),
            "BigPlayerRate": Decimal(utils.round_down_to_decimal_places_string(big_player_rate, 3)),
            "OfferList": offer_list,
        }

        return result


    def calculate_used_balance_percentage(self, account_balance: dict, my_active_open_order: dict) -> Decimal:
        total_balance = account_balance["Balance"]

        available_balance_include_open_order = account_balance["Available"]
        if my_active_open_order is not None:
            available_balance_include_open_order += my_active_open_order["Size"] - my_active_open_order["FilledSize"]

        return (total_balance - available_balance_include_open_order) / total_balance


    def calculate_minimum_daily_interest_rate(self, balance_utilization_rate: Decimal) -> Decimal:
        if balance_utilization_rate >= 80:
            return self.config.step_bot.min_80p_daily_interest_rate
        if balance_utilization_rate >= 60:
            return self.config.step_bot.min_60p_daily_interest_rate
        if balance_utilization_rate >= 40:
            return self.config.step_bot.min_40p_daily_interest_rate

        return self.config.step_bot.min_daily_interest_rate


    def calculate_my_optimal_daily_interest_rate(self, market_data: dict, my_active_open_orders: list, min_daily_interest_rate: Decimal) -> Decimal:
        my_lowest_daily_interest_rate = None
        if len(my_active_open_orders) >= 1:
            my_lowest_daily_interest_rate = my_active_open_orders[0]["DailyInterestRate"]

        happy_rate = self.config.step_bot.happy_daily_interest_rate
        big_player_rate = market_data["BigPlayerRate"]

        happy_cumulative_size_threshold = self.config.step_bot.happy_cumulative_size_threshold

        happy_cumulative_size = Decimal(0)
        offer_list = market_data["OfferList"]
        for line in offer_list:
            line_rate = line["Rate"]
            line_size = line["Size"]

            if line_rate < min_daily_interest_rate:
                continue

            if line_rate == big_player_rate and line_rate == min_daily_interest_rate:
                return line_rate

            if line_rate >= big_player_rate:
                if my_lowest_daily_interest_rate is not None and line_rate == my_lowest_daily_interest_rate:
                    return line_rate
                return big_player_rate - Decimal("0.001")

            if line_rate >= happy_rate:
                happy_cumulative_size += line_size
                if happy_cumulative_size > happy_cumulative_size_threshold:
                    if my_lowest_daily_interest_rate is not None and line_rate == my_lowest_daily_interest_rate:
                        return line_rate
                    return line_rate - Decimal("0.001")

        if len(offer_list) > 0:
            rate = offer_list[-1]["Rate"]
            if rate < min_daily_interest_rate:
                return min_daily_interest_rate
            else:
                return rate

        return Decimal(2)


    def calculate_lending_size(self, total_balance: Decimal, available_balance: Decimal) -> Decimal:
        minimum_size = total_balance * self.config.step_bot.min_lending_size_ratio
        if minimum_size < self.config.currency_minimum_lending_size:
            minimum_size = self.config.currency_minimum_lending_size

        maximum_size = total_balance * self.config.step_bot.max_lending_size_ratio
        if maximum_size < self.config.currency_minimum_lending_size:
            maximum_size = self.config.currency_minimum_lending_size

        available_balance = Decimal(utils.round_down_to_decimal_places_string(available_balance, self.config.currency_lending_decimal_places))
        minimum_size = Decimal(utils.round_down_to_decimal_places_string(minimum_size, self.config.currency_lending_decimal_places))
        maximum_size = Decimal(utils.round_down_to_decimal_places_string(maximum_size, self.config.currency_lending_decimal_places))

        self.log(f"MinimumSize=[{minimum_size}] MaximumSize=[{maximum_size}] AvailableBalance=[{available_balance}]")
        if available_balance < minimum_size:
            return Decimal(utils.round_down_to_decimal_places_string(0, self.config.currency_lending_decimal_places))

        result = available_balance
        if available_balance > maximum_size:
            result = maximum_size

        return result
