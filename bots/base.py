from abc import abstractmethod
from decimal import Decimal

from kucoin.client import User as UserClient
from kucoin.client import Margin as MarginClient

import utils
from configuration import AccountConfiguration


class BaseBot:

    EPOCH_PER_HOUR = 60 * 60
    EPOCH_PER_DAY = EPOCH_PER_HOUR * 24

    config: AccountConfiguration
    user_client: UserClient
    margin_client: MarginClient

    response_log: list = None

    all_unsettled_orders: list = None


    def __init__(self, config: AccountConfiguration) -> None:
        self.config = config

        self.user_client = UserClient(
            key=self.config.api_key,
            secret=self.config.api_secret,
            passphrase=self.config.api_passphrase,
            is_sandbox=False,
            url=self.config.base_url
        )

        self.margin_client = MarginClient(
            key=self.config.api_key,
            secret=self.config.api_secret,
            passphrase=self.config.api_passphrase,
            is_sandbox=False,
            url=self.config.base_url
        )


    @abstractmethod
    def execute(self, should_execute: bool) -> None:
        ...


    def log(self, message) -> None:
        print(message)
        if self.response_log is not None:
            self.response_log.append(message)


    def get_account_balance(self) -> dict:
        account_response = self.user_client.get_account_list(self.config.currency, "main")

        total_balance = Decimal(account_response[0]["balance"])
        available_balance = Decimal(account_response[0]["available"])
        total_accrued_interest = Decimal(0)
        culumative_weighted_interest_rate = Decimal(0)
        culumative_unsettled_size = Decimal(0)

        all_unsettled_orders = self.get_all_unsettled_orders()

        for order in all_unsettled_orders:
            order_total_size = Decimal(order["size"])
            order_remaining_size = order_total_size - Decimal(order["repaid"])
            total_balance += order_remaining_size
            total_accrued_interest += Decimal(order["accruedInterest"])

            order_daily_interest_rate = Decimal(order["dailyIntRate"])
            culumative_weighted_interest_rate += order_remaining_size * order_daily_interest_rate
            culumative_unsettled_size += order_remaining_size

        unrealized_accrued_interest = total_accrued_interest * (100 - self.config.lending_fee_rate) / 100

        reserved_balance = self.config.reserved_balance
        if reserved_balance > 0:
            reserved_percentage = utils.round_down_to_decimal_places(reserved_balance / total_balance * 100, 2)
            if reserved_percentage > 100:
                reserved_percentage = 100
            self.log(f"ReservedBalance=[{reserved_balance}] ReservedPercentage=[{reserved_percentage}%]")
            total_balance -= reserved_balance
            available_balance -= reserved_balance

        if culumative_weighted_interest_rate and culumative_unsettled_size > 0:
            average_daily_interest_rate = culumative_weighted_interest_rate / culumative_unsettled_size * 100
        else:
            average_daily_interest_rate = Decimal(0)

        if culumative_weighted_interest_rate and total_balance > 0:
            effective_daily_interest_rate_on_total_balance = culumative_weighted_interest_rate / total_balance * (100 - self.config.lending_fee_rate)
        else:
            effective_daily_interest_rate_on_total_balance = Decimal(0)

        result = {
            "Balance": total_balance,
            "Available": available_balance,
            "UnrealizedAccruedInterest": unrealized_accrued_interest,
            "AverageDailyInterestRate": average_daily_interest_rate,
            "EffectiveDailyInterestRateOnTotalBalance": effective_daily_interest_rate_on_total_balance,
        }

        return result


    def get_unsettled_orders(self, current_page: int) -> list:
        return self.margin_client.get_active_list(currency=self.config.currency, currentPage=current_page, pageSize=50)


    def get_all_unsettled_orders(self):
        if self.all_unsettled_orders is not None:
            return self.all_unsettled_orders

        self.all_unsettled_orders = list()

        active_order_list_current_page = 1
        while True:
            unsettled_orders_response = self.get_unsettled_orders(current_page=active_order_list_current_page)

            if unsettled_orders_response["totalNum"] == 0:
                break

            self.all_unsettled_orders += unsettled_orders_response["items"]

            if unsettled_orders_response["totalPage"] == active_order_list_current_page:
                break

            active_order_list_current_page += 1

        return self.all_unsettled_orders


    def get_my_active_open_orders(self) -> list:
        active_open_orders_response = self.margin_client.get_active_order(currency=self.config.currency)

        if active_open_orders_response["totalNum"] == 0:
            return list()

        result = list()
        for order in active_open_orders_response["items"]:
            order_info = {
                "OrderId": order["orderId"],
                "DailyInterestRate": Decimal(utils.round_down_to_decimal_places_string(Decimal(order["dailyIntRate"]) * 100, 3)),
                "Size": Decimal(order["size"]),
                "FilledSize": Decimal(order["filledSize"]),
            }
            result.append(order_info)

        return result


    def get_lending_market_data(self) -> list:
        return self.margin_client.get_lending_market(self.config.currency)


    def create_lend_order(self, daily_interest_rate: Decimal, size: Decimal, term: int) -> None:
        daily_interest_rate_str = utils.round_down_to_decimal_places_string(daily_interest_rate / 100, 5)

        try:
            self.margin_client.create_lend_order(self.config.currency, str(size), daily_interest_rate_str, term)
            effective_daily_interest_rate = self.calculate_effective_daily_interest_rate(daily_interest_rate)
            effective_yeary_interest_rate = effective_daily_interest_rate * 365
            self.log(f"Created lend order: DailyInterestRate=[{daily_interest_rate}%] Size=[{size}] Term=[{term}] EffectiveDailyInterestRate=[{utils.round_down_to_decimal_places_string(effective_daily_interest_rate, 3)}%] EffectiveYearlyInterestRate=[{utils.round_down_to_decimal_places_string(effective_yeary_interest_rate, 3)}%]")
        except Exception as ex:
            self.log(f"Failed to create lend order: DailyInterestRate=[{daily_interest_rate}%] Size=[{size}] Term=[{term}] Error:[{repr(ex)}]")


    def cancel_lend_order(self, order_id: str):
        self.margin_client.cancel_lend_order(order_id)


    def calculate_effective_daily_interest_rate(self, daily_interest_rate: Decimal) -> Decimal:
        return daily_interest_rate * (100 - self.config.lending_fee_rate) / 100
