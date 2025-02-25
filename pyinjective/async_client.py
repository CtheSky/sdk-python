import os
import time
import grpc
from typing import List, Optional, Tuple, Union

from .exceptions import NotFoundError, EmptyMsgError

from .proto.cosmos.base.abci.v1beta1 import abci_pb2 as abci_type

from .proto.cosmos.base.tendermint.v1beta1 import (
    query_pb2_grpc as tendermint_query_grpc,
    query_pb2 as tendermint_query,
)
from .proto.cosmos.auth.v1beta1 import (
    query_pb2_grpc as auth_query_grpc,
    query_pb2 as auth_query,
    auth_pb2 as auth_type,
)
from .proto.cosmos.authz.v1beta1 import (
    query_pb2_grpc as authz_query_grpc,
    query_pb2 as authz_query,
    authz_pb2 as authz_type,
)
from .proto.cosmos.tx.v1beta1 import (
    service_pb2_grpc as tx_service_grpc,
    service_pb2 as tx_service,
)
from .proto.exchange import (
    injective_accounts_rpc_pb2 as exchange_accounts_rpc_pb,
    injective_accounts_rpc_pb2_grpc as exchange_accounts_rpc_grpc,
    injective_oracle_rpc_pb2 as oracle_rpc_pb,
    injective_oracle_rpc_pb2_grpc as oracle_rpc_grpc,
    injective_insurance_rpc_pb2 as insurance_rpc_pb,
    injective_insurance_rpc_pb2_grpc as insurance_rpc_grpc,
    injective_spot_exchange_rpc_pb2 as spot_exchange_rpc_pb,
    injective_spot_exchange_rpc_pb2_grpc as spot_exchange_rpc_grpc,
    injective_derivative_exchange_rpc_pb2 as derivative_exchange_rpc_pb,
    injective_derivative_exchange_rpc_pb2_grpc as derivative_exchange_rpc_grpc,
    injective_meta_rpc_pb2 as exchange_meta_rpc_pb,
    injective_meta_rpc_pb2_grpc as exchange_meta_rpc_grpc,
    injective_explorer_rpc_pb2 as explorer_rpc_pb,
    injective_explorer_rpc_pb2_grpc as explorer_rpc_grpc,
    injective_auction_rpc_pb2 as auction_rpc_pb,
    injective_auction_rpc_pb2_grpc as auction_rpc_grpc
)

from .constant import Network

TIMEOUT = int(os.environ.get('INJ_GRPC_TIMEOUT') or 8)


class UnaryUnaryWithTimeout(grpc.aio.UnaryUnaryClientInterceptor):
    """
    An Interceptor to add timeout option on unary unary calls

    it reads environment variables INJ_GRPC_TIMEOUT in seconds
    """

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        new_details = grpc.aio.ClientCallDetails(
            client_call_details.method,
            TIMEOUT,
            client_call_details.metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready
        )
        return await continuation(new_details, request)


class AsyncClient:
    def __init__(
            self,
            network: Network,
            insecure: bool = False,
            credentials: grpc.ChannelCredentials = None,
    ):
        # chain stubs
        self.chain_channel = (
            grpc.aio.insecure_channel(
                network.grpc_endpoint,
                interceptors=[UnaryUnaryWithTimeout()]
            )
            if insecure
            else grpc.aio.secure_channel(
                network.grpc_endpoint,
                credentials or grpc.ssl_channel_credentials(),
                interceptors=[UnaryUnaryWithTimeout()]
            )
        )
        self.stubCosmosTendermint = tendermint_query_grpc.ServiceStub(self.chain_channel)
        self.stubAuth = auth_query_grpc.QueryStub(self.chain_channel)
        self.stubTx = tx_service_grpc.ServiceStub(self.chain_channel)

        # exchange stubs
        self.exchange_channel = (
            grpc.aio.insecure_channel(
                network.grpc_exchange_endpoint,
                interceptors=[UnaryUnaryWithTimeout()]
            )
            if insecure
            else grpc.aio.secure_channel(
                network.grpc_endpoint,
                credentials or grpc.ssl_channel_credentials(),
                interceptors=[UnaryUnaryWithTimeout()]
            )
        )
        self.stubMeta = exchange_meta_rpc_grpc.InjectiveMetaRPCStub(self.exchange_channel)
        self.stubExchangeAccount = exchange_accounts_rpc_grpc.InjectiveAccountsRPCStub(self.exchange_channel)
        self.stubOracle = oracle_rpc_grpc.InjectiveOracleRPCStub(self.exchange_channel)
        self.stubInsurance = insurance_rpc_grpc.InjectiveInsuranceRPCStub(self.exchange_channel)
        self.stubSpotExchange = spot_exchange_rpc_grpc.InjectiveSpotExchangeRPCStub(self.exchange_channel)
        self.stubDerivativeExchange = derivative_exchange_rpc_grpc.InjectiveDerivativeExchangeRPCStub(self.exchange_channel)
        self.stubExplorer = explorer_rpc_grpc.InjectiveExplorerRPCStub(self.exchange_channel)
        self.stubAuction = auction_rpc_grpc.InjectiveAuctionRPCStub(self.exchange_channel)

    # default client methods
    async def get_latest_block(self) -> tendermint_query.GetLatestBlockResponse:
        return await self.stubCosmosTendermint.GetLatestBlock(tendermint_query.GetLatestBlockRequest())

    async def get_account(self, address: str) -> Optional[auth_type.BaseAccount]:
        try:
            account_any = await self.stubAuth.Account(auth_query.QueryAccountRequest(address=address)).account
            account = auth_type.BaseAccount()
            if account_any.Is(account.DESCRIPTOR):
                account_any.Unpack(account)
                return account
        except:
            return None

    async def get_request_id_by_tx_hash(self, tx_hash: bytes) -> List[int]:
        tx = await self.stubTx.GetTx(tx_service.GetTxRequest(hash=tx_hash))
        request_ids = []
        for tx in tx.tx_response.logs:
            request_event = [event for event in tx.events if event.type == "request" or event.type == "report"]
            if len(request_event) == 1:
                attrs = request_event[0].attributes
                attr_id = [attr for attr in attrs if attr.key == "id"]
                if len(attr_id) == 1:
                    request_id = attr_id[0].value
                    request_ids.append(int(request_id))
        if len(request_ids) == 0:
            raise NotFoundError("Request Id is not found")
        return request_ids

    async def simulate_tx(self, tx_byte: bytes) -> Tuple[Union[abci_type.SimulationResponse, grpc.RpcError], bool]:
        try:
            return (await self.stubTx.Simulate(
                tx_service.SimulateRequest(tx_bytes=tx_byte)
            ), True)
        except grpc.RpcError as err:
            return err, False

    async def send_tx_sync_mode(self, tx_byte: bytes) -> abci_type.TxResponse:
        result = await self.stubTx.BroadcastTx(
            tx_service.BroadcastTxRequest(tx_bytes=tx_byte, mode=tx_service.BroadcastMode.BROADCAST_MODE_SYNC)
        )
        return result.tx_response

    async def send_tx_async_mode(self, tx_byte: bytes) -> abci_type.TxResponse:
        result = await self.stubTx.BroadcastTx(
            tx_service.BroadcastTxRequest(tx_bytes=tx_byte, mode=tx_service.BroadcastMode.BROADCAST_MODE_ASYNC)
        )
        return result.tx_response

    async def send_tx_block_mode(self, tx_byte: bytes) -> abci_type.TxResponse:
        result = await self.stubTx.BroadcastTx(
            tx_service.BroadcastTxRequest(tx_bytes=tx_byte, mode=tx_service.BroadcastMode.BROADCAST_MODE_BLOCK)
        )
        return result.tx_response

    async def get_chain_id(self) -> str:
        latest_block = await self.get_latest_block()
        return latest_block.block.header.chain_id

    async def get_grants(self, granter: str, grantee: str, **kwargs):
        return await self.stubAuthz.Grants(
            authz_query.QueryGrantsRequest(
                granter=granter, grantee=grantee, msg_type_url=kwargs.get("msg_type_url")))

    # Injective Exchange client methods

    # Auction RPC

    async def get_auction(self, bid_round: int):
        req = auction_rpc_pb.AuctionRequest(round=bid_round)
        return await self.stubAuction.AuctionEndpoint(req)

    async def get_auctions(self):
        req = auction_rpc_pb.AuctionsRequest()
        return await self.stubAuction.Auctions(req)

    async def stream_bids(self):
        req = auction_rpc_pb.StreamBidsRequest()
        return self.stubAuction.StreamBids(req)


    # Meta RPC

    async def ping(self):
        req = exchange_meta_rpc_pb.PingRequest()
        return await self.stubMeta.Ping(req)

    async def version(self):
        req = exchange_meta_rpc_pb.VersionRequest()
        return await self.stubMeta.Version(req)

    async def info(self):
        req = exchange_meta_rpc_pb.InfoRequest(
            timestamp=int(time.time() * 1000),
        )
        return await self.stubMeta.Info(req)

    async def stream_keepalive(self):
        req = exchange_meta_rpc_pb.StreamKeepaliveRequest()
        return self.stubMeta.StreamKeepalive(req)

    # Explorer RPC

    async def get_tx_by_hash(self, tx_hash: str):
        req = explorer_rpc_pb.GetTxByTxHashRequest(hash=tx_hash)
        return await self.stubExplorer.GetTxByTxHash(req)

    #AccountsRPC

    async def stream_subaccount_balance(self, subaccount_id: str):
        req = exchange_accounts_rpc_pb.StreamSubaccountBalanceRequest(subaccount_id=subaccount_id)
        return self.stubExchangeAccount.StreamSubaccountBalance(req)

    async def get_subaccount_balance(self, subaccount_id: str, denom: str):
        req = exchange_accounts_rpc_pb.SubaccountBalanceRequest(subaccount_id=subaccount_id, denom=denom)
        return await self.stubExchangeAccount.SubaccountBalanceEndpoint(req)

    async def get_subaccount_list(self, account_address: str):
        req = exchange_accounts_rpc_pb.SubaccountsListRequest(account_address=account_address)
        return await self.stubExchangeAccount.SubaccountsList(req)

    async def get_subaccount_balances_list(self, subaccount_id: str):
        req = exchange_accounts_rpc_pb.SubaccountBalancesListRequest(subaccount_id=subaccount_id)
        return await self.stubExchangeAccount.SubaccountBalancesList(req)

    async def get_subaccount_history(self, subaccount_id: str, **kwargs):
        req = exchange_accounts_rpc_pb.SubaccountHistoryRequest(subaccount_id=subaccount_id, denom=kwargs.get("denom"), transfer_types=kwargs.get("transfer_types"))
        return await self.stubExchangeAccount.SubaccountHistory(req)

    async def get_subaccount_order_summary(self, subaccount_id: str, **kwargs):
        req = exchange_accounts_rpc_pb.SubaccountOrderSummaryRequest(subaccount_id=subaccount_id, order_direction=kwargs.get("order_direction"), market_id=kwargs.get("market_id"))
        return await self.stubExchangeAccount.SubaccountOrderSummary(req)

    async def get_order_states(
        self,
        **kwargs
    ):
        req = exchange_accounts_rpc_pb.OrderStatesRequest(
            spot_order_hashes=kwargs.get("spot_order_hashes"),
            derivative_order_hashes=kwargs.get("derivative_order_hashes"),
        )
        return await self.stubExchangeAccount.OrderStates(req)

    async def get_portfolio(self, account_address: str):
        req = exchange_accounts_rpc_pb.PortfolioRequest(account_address=account_address)
        return await self.stubExchangeAccount.Portfolio(req)

    async def get_rewards(self, **kwargs):
        req = exchange_accounts_rpc_pb.RewardsRequest(account_address=kwargs.get("account_address"), epoch=kwargs.get("epoch"))
        return await self.stubExchangeAccount.Rewards(req)


    # OracleRPC

    async def stream_oracle_prices(self, base_symbol: str, quote_symbol: str, oracle_type: str):
        req = oracle_rpc_pb.StreamPricesRequest(base_symbol=base_symbol, quote_symbol=quote_symbol, oracle_type=oracle_type)
        return self.stubOracle.StreamPrices(req)

    async def get_oracle_prices(self, base_symbol: str, quote_symbol: str, oracle_type: str, oracle_scale_factor: int):
        req = oracle_rpc_pb.PriceRequest(base_symbol=base_symbol, quote_symbol=quote_symbol, oracle_type=oracle_type,
                oracle_scale_factor=oracle_scale_factor)
        return await self.stubOracle.Price(req)

    async def get_oracle_list(self):
        req = oracle_rpc_pb.OracleListRequest()
        return await self.stubOracle.OracleList(req)

    # InsuranceRPC

    async def get_insurance_funds(self):
        req = insurance_rpc_pb.FundsRequest()
        return await self.stubInsurance.Funds(req)

    async def get_redemptions(self, **kwargs):
        req = insurance_rpc_pb.RedemptionsRequest(redeemer=kwargs.get("redeemer"), redemption_denom=kwargs.get("redemption_denom"), status=kwargs.get("status"))
        return await self.stubInsurance.Redemptions(req)


    # SpotRPC

    async def get_spot_market(self, market_id: str):
        req = spot_exchange_rpc_pb.MarketRequest(market_id=market_id)
        return await self.stubSpotExchange.Market(req)

    async def get_spot_markets(self, **kwargs):
        req = spot_exchange_rpc_pb.MarketsRequest(market_status=kwargs.get("market_status"), base_denom=kwargs.get("base_denom"), quote_denom=kwargs.get("quote_denom"))
        return await self.stubSpotExchange.Markets(req)

    async def stream_spot_markets(self):
        req = spot_exchange_rpc_pb.StreamMarketsRequest()
        return self.stubSpotExchange.StreamMarkets(req)

    async def get_spot_orderbook(self, market_id: str):
        req = spot_exchange_rpc_pb.OrderbookRequest(market_id=market_id)
        return await self.stubSpotExchange.Orderbook(req)

    async def get_spot_orders(self, market_id: str, **kwargs):
        req = spot_exchange_rpc_pb.OrdersRequest(market_id=market_id, order_side=kwargs.get("order_side"), subaccount_id=kwargs.get("subaccount_id"))
        return await self.stubSpotExchange.Orders(req)

    async def get_spot_trades(self, market_id: str, **kwargs):
        req = spot_exchange_rpc_pb.TradesRequest(market_id=market_id, execution_side=kwargs.get("execution_side"), direction=kwargs.get("direction"), subaccount_id=kwargs.get("subaccount_id"), skip=kwargs.get("skip"), limit=kwargs.get("limit"))
        return await self.stubSpotExchange.Trades(req)

    async def stream_spot_orderbook(self, market_id: str):
        req = spot_exchange_rpc_pb.StreamOrderbookRequest(market_ids=[market_id])
        return self.stubSpotExchange.StreamOrderbook(req)

    async def stream_spot_orderbooks(self, market_ids: List[str]):
        req = spot_exchange_rpc_pb.StreamOrderbookRequest(market_ids=market_ids)
        return self.stubSpotExchange.StreamOrderbook(req)


    async def stream_spot_orders(self, market_id: str, **kwargs):
        req = spot_exchange_rpc_pb.StreamOrdersRequest(market_id=market_id, order_side=kwargs.get("order_side"), subaccount_id=kwargs.get("subaccount_id"))
        return self.stubSpotExchange.StreamOrders(req)

    async def stream_spot_trades(self, market_id: str, **kwargs):
        req = spot_exchange_rpc_pb.StreamTradesRequest(market_id=market_id, execution_side=kwargs.get("execution_side"), direction=kwargs.get("direction"), subaccount_id=kwargs.get("subaccount_id"), skip=kwargs.get("skip"), limit=kwargs.get("limit"))
        return self.stubSpotExchange.StreamTrades(req)

    async def get_spot_subaccount_orders(self, subaccount_id: str, **kwargs):
        req = spot_exchange_rpc_pb.SubaccountOrdersListRequest(subaccount_id=subaccount_id, market_id=kwargs.get("market_id"))
        return await self.stubSpotExchange.SubaccountOrdersList(req)

    async def get_spot_subaccount_trades(self, subaccount_id: str, **kwargs):
        req = spot_exchange_rpc_pb.SubaccountTradesListRequest(subaccount_id=subaccount_id, market_id=kwargs.get("market_id"), execution_type=kwargs.get("execution_type"), direction=kwargs.get("direction"))
        return await self.stubSpotExchange.SubaccountTradesList(req)

    # DerivativeRPC

    async def get_derivative_market(self, market_id: str):
        req = derivative_exchange_rpc_pb.MarketRequest(market_id=market_id)
        return await self.stubDerivativeExchange.Market(req)

    async def get_derivative_markets(self, **kwargs):
        req = derivative_exchange_rpc_pb.MarketsRequest(market_status=kwargs.get("market_status"), quote_denom=kwargs.get("quote_denom"))
        return await self.stubDerivativeExchange.Markets(req)

    async def stream_derivative_markets(self):
        req = derivative_exchange_rpc_pb.StreamMarketRequest()
        return self.stubDerivativeExchange.StreamMarket(req)

    async def get_derivative_orderbook(self, market_id: str):
        req = derivative_exchange_rpc_pb.OrderbookRequest(market_id=market_id)
        return await self.stubDerivativeExchange.Orderbook(req)

    async def get_derivative_orders(self, market_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.OrdersRequest(market_id=market_id, order_side=kwargs.get("order_side"), subaccount_id=kwargs.get("subaccount_id"))
        return await self.stubDerivativeExchange.Orders(req)

    async def get_derivative_trades(self, market_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.TradesRequest(market_id=market_id, subaccount_id=kwargs.get("subaccount_id"), execution_side=kwargs.get("execution_side"), direction=kwargs.get("direction"), skip=kwargs.get("skip"), limit=kwargs.get("limit"))
        return await self.stubDerivativeExchange.Trades(req)

    async def stream_derivative_orderbook(self, market_id: str):
        req = derivative_exchange_rpc_pb.StreamOrderbookRequest(market_ids=[market_id])
        return self.stubDerivativeExchange.StreamOrderbook(req)

    async def stream_derivative_orderbooks(self, market_ids: List[str]):
        req = derivative_exchange_rpc_pb.StreamOrderbookRequest(market_ids=market_ids)
        return self.stubDerivativeExchange.StreamOrderbook(req)

    async def stream_derivative_orders(self, market_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.StreamOrdersRequest(market_id=market_id, order_side=kwargs.get("order_side"), subaccount_id=kwargs.get("subaccount_id"))
        return self.stubDerivativeExchange.StreamOrders(req)

    async def stream_derivative_trades(self, market_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.StreamTradesRequest(market_id=market_id, subaccount_id=kwargs.get("subaccount_id"), execution_side=kwargs.get("execution_side"), direction=kwargs.get("direction"), skip=kwargs.get("skip"), limit=kwargs.get("limit"))
        return self.stubDerivativeExchange.StreamTrades(req)

    async def get_derivative_positions(self, market_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.PositionsRequest(market_id=market_id, subaccount_id=kwargs.get("subaccount_id"))
        return await self.stubDerivativeExchange.Positions(req)

    async def stream_derivative_positions(self, market_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.StreamPositionsRequest(market_id=market_id, subaccount_id=kwargs.get("subaccount_id"))
        return self.stubDerivativeExchange.StreamPositions(req)

    async def get_derivative_liquidable_positions(self, **kwargs):
        req = derivative_exchange_rpc_pb.LiquidablePositionsRequest(market_id=kwargs.get("market_id"))
        return await self.stubDerivativeExchange.LiquidablePositions(req)

    async def get_derivative_subaccount_orders(self, subaccount_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.SubaccountOrdersListRequest(subaccount_id=subaccount_id, market_id=kwargs.get("market_id"))
        return await self.stubDerivativeExchange.SubaccountOrdersList(req)

    async def get_derivative_subaccount_trades(self, subaccount_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.SubaccountTradesListRequest(subaccount_id=subaccount_id, market_id=kwargs.get("market_id"), execution_type=kwargs.get("execution_type"), direction=kwargs.get("direction"))
        return await self.stubDerivativeExchange.SubaccountTradesList(req)

    async def get_funding_payments(self, subaccount_id: str, **kwargs):
        req = derivative_exchange_rpc_pb.FundingPaymentsRequest(subaccount_id=subaccount_id, market_id=kwargs.get("market_id"), skip=kwargs.get("skip"), limit=kwargs.get("limit"))
        return await self.stubDerivativeExchange.FundingPayments(req)