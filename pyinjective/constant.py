import os
from configparser import ConfigParser

MAX_CLIENT_ID_LENGTH = 128
MAX_DATA_SIZE = 256
MAX_MEMO_CHARACTERS = 256

devnet_config = ConfigParser()
devnet_config.read(os.path.join(os.path.dirname(__file__), 'denoms_devnet.ini'))

testnet_config = ConfigParser()
testnet_config.read(os.path.join(os.path.dirname(__file__), 'denoms_testnet.ini'))

mainnet_config = ConfigParser()
mainnet_config.read(os.path.join(os.path.dirname(__file__), 'denoms_mainnet.ini'))

class Denom:
    def __init__(
        self,
        description: str,
        base: int,
        quote: int,
        min_price_tick_size: float,
        min_quantity_tick_size: float
    ):
        self.description = description
        self.base = base
        self.quote = quote
        self.min_price_tick_size = min_price_tick_size
        self.min_quantity_tick_size = min_quantity_tick_size

    @classmethod
    def load_market(cls, network, market_id):
        if network == 'devnet':
            config = devnet_config
        elif network == 'testnet':
            config = testnet_config
        else:
            config =mainnet_config

        return cls(
            description=config[market_id]['description'],
            base=int(config[market_id]['base']),
            quote=int(config[market_id]['quote']),
            min_price_tick_size=float(config[market_id]['min_price_tick_size']),
            min_quantity_tick_size=float(config[market_id]['min_quantity_tick_size']),
        )

    @classmethod
    def load_peggy_denom(cls, network, symbol):
        if network == 'devnet':
            config = devnet_config
        elif network == 'local':
            config = devnet_config
        elif network == 'testnet':
            config = testnet_config
        else:
            config = mainnet_config
        return config[symbol]['peggy_denom'], int(config[symbol]['decimals'])


class Network:
    def __init__(
        self,
        lcd_endpoint: str ,
        grpc_endpoint: str ,
        grpc_exchange_endpoint: str ,
        chain_id: str ,
        fee_denom: str ,
        env: str
    ):
        self.lcd_endpoint = lcd_endpoint
        self.grpc_endpoint = grpc_endpoint
        self.grpc_exchange_endpoint = grpc_exchange_endpoint
        self.chain_id = chain_id
        self.fee_denom = fee_denom
        self.env = env

    @classmethod
    def devnet(cls):
        return cls(
            lcd_endpoint='https://devnet.lcd.injective.dev',
            grpc_endpoint='devnet.injective.dev:9900',
            grpc_exchange_endpoint='devnet.injective.dev:9910',
            chain_id='injective-777',
            fee_denom='inj',
            env='devnet'
        )

    @classmethod
    def testnet(cls, node='sentry0'):
        nodes = ['sentry0', 'sentry1']
        if node not in nodes:
            raise ValueError("Must be one of {}".format(nodes))

        return cls(
            lcd_endpoint="https://testnet.lcd.injective.dev",
            grpc_endpoint=f"{node}.injective.dev:9900",
            grpc_exchange_endpoint=f"{node}.injective.dev:9910",
            chain_id='injective-888',
            fee_denom='inj',
            env='testnet'
        )

    @classmethod
    def mainnet(cls, node='sentry2'):
        nodes = [
            'sentry0',  # us, prod
            'sentry1',  # us, prod
            'sentry2',  # us, staging
            'sentry3',  # tokyo, prod,
            'sentry4',
            'sentry.cd',  # dedicated github-runner
            'asymm_inner_node',
            'asymm_outer_node',

        ]
        if node not in nodes:
            raise ValueError("Must be one of {}".format(nodes))
        if node == 'asymm_inner_node':
            return cls(
                lcd_endpoint="http://172.31.37.139:10337",
                grpc_endpoint="172.31.37.139:9900",
                grpc_exchange_endpoint="172.31.37.139:9910",
                chain_id='injective-1',
                fee_denom='inj',
                env='mainnet'
            )
        if node == 'asymm_outer_node':
            return cls(
                lcd_endpoint="http://18.183.209.52:10337",
                grpc_endpoint="18.183.209.52:9900",
                grpc_exchange_endpoint="18.183.209.52:9910",
                chain_id='injective-1',
                fee_denom='inj',
                env='mainnet'
            )

        return cls(
            lcd_endpoint="https://lcd.injective.network",
            grpc_endpoint=f"{node}.injective.network:9900",
            grpc_exchange_endpoint=f"{node}.injective.network:9910",
            chain_id='injective-1',
            fee_denom='inj',
            env='mainnet'
        )

    @classmethod
    def local(cls):
        return cls(
            lcd_endpoint="localhost:10337",
            grpc_endpoint="localhost:9900",
            grpc_exchange_endpoint="localhost:9910",
            chain_id='injective-1',
            fee_denom='inj',
            env='local'
        )

    @classmethod
    def mainnet_through_self_hosted_node(cls):
        return cls(
            lcd_endpoint="http://172.31.42.171:10337",
            grpc_endpoint="172.31.42.171:9900",
            grpc_exchange_endpoint="172.31.42.171:9910",
            chain_id='injective-1',
            fee_denom='inj',
            env='mainnet'
        )

    def string(self):
        return self.env
