from decimal import Decimal


class StepBotConfiguration:

    parent_name: str

    min_lending_size_ratio: Decimal
    max_lending_size_ratio: Decimal

    min_daily_interest_rate: Decimal
    min_40p_daily_interest_rate: Decimal
    min_60p_daily_interest_rate: Decimal
    min_80p_daily_interest_rate: Decimal
    big_player_size_threshold: Decimal

    happy_daily_interest_rate: Decimal
    happy_cumulative_size_threshold: Decimal

    term_14_daily_interest_rate: Decimal
    term_28_daily_interest_rate: Decimal

    def __init__(self, parent_name: str, doc) -> None:
        data = doc.to_dict()

        self.parent_name = parent_name

        self.min_lending_size_ratio = Decimal(data["minimum_lending_size_ratio"])
        self.max_lending_size_ratio = Decimal(data["maximum_lending_size_ratio"])

        self.min_daily_interest_rate = Decimal(data["minimum_daily_interest_rate"])
        self.min_40p_daily_interest_rate = Decimal(data["40p_minimum_daily_interest_rate"])
        self.min_60p_daily_interest_rate = Decimal(data["60p_minimum_daily_interest_rate"])
        self.min_80p_daily_interest_rate = Decimal(data["80p_minimum_daily_interest_rate"])
        self.big_player_size_threshold = Decimal(data["big_player_size_threshold"])

        if self.max_lending_size_ratio < self.min_lending_size_ratio:
            print(f"MaxLendingSizeRatio=[{self.max_lending_size_ratio}%] is lower than MinLendingSizeRatio=[{self.min_lending_size_ratio}%]. Will use MinLendingSizeRatio instead.")
            self.max_lending_size_ratio = self.min_lending_size_ratio

        self.happy_daily_interest_rate = Decimal(data["happy_daily_interest_rate"])
        self.happy_cumulative_size_threshold = Decimal(data["happy_cumulative_size_threshold"])

        if self.happy_daily_interest_rate < self.min_daily_interest_rate:
            print(f"HappyDailyInterestRate=[{self.happy_daily_interest_rate}%] is lower than MinDailyInterestRate=[{self.min_daily_interest_rate}%]. Will use MinDailyInterestRate instead.")
            self.happy_daily_interest_rate = self.min_daily_interest_rate

        self.term_14_daily_interest_rate = Decimal(data["term_14_daily_interest_rate"])
        self.term_28_daily_interest_rate = Decimal(data["term_28_daily_interest_rate"])


class AccountConfiguration:

    name: str
    active: bool
    kill: bool

    base_url: str
    api_key: str
    api_secret: str
    api_passphrase: str

    currency: str
    currency_precision_decimal_places: int
    currency_earning_report_decimal_places: int
    currency_lending_decimal_places: int
    currency_minimum_lending_size: Decimal
    lending_fee_rate: Decimal

    reserved_balance: Decimal

    step_bot: StepBotConfiguration

    def __init__(self, doc, accounts_ref) -> None:
        data = doc.to_dict()

        self.active = bool(data["active"])
        if not self.active:
            return

        self.name = data["name"]
        self.kill = bool(data["kill"])

        self.base_url = data["base_url"]
        self.api_key = data["api_key"]
        self.api_secret = data["api_secret"]
        self.api_passphrase = data["api_passphrase"]

        self.currency = data["currency"]
        self.currency_precision_decimal_places = int(data["currency_precision_decimal_places"])
        self.currency_earning_report_decimal_places = int(data["currency_earning_report_decimal_places"])

        self.currency_minimum_lending_size = Decimal(data["currency_minimum_lending_size"])
        self.currency_lending_decimal_places = int(data["currency_lending_decimal_places"])
        self.lending_fee_rate = Decimal(data["lending_fee_rate"])

        self.reserved_balance = Decimal(data["reserved_balance"])

        step_bot_doc = accounts_ref.document(doc.id).collection(u"bots").document(u"step").get()
        self.step_bot = PistolBotConfiguration(self.name, step_bot_doc)


class Configuration:

    accounts: list

    def __init__(self, db) -> None:
        self.accounts = list()

        accounts_ref = db.collection(u"kucoin").document(u"lending").collection(u"accounts")
        for account_doc in accounts_ref.stream():
            self.accounts.append(AccountConfiguration(account_doc, accounts_ref))
