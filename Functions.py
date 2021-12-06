from __future__ import annotations
import os, yaml, json, ipysheet, math
from algosdk.v2client.algod import AlgodClient
from tinyman.v1.client import TinymanMainnetClient
from tinyman.v1.pools import get_pool_info_from_account_info

def dict_nested_get(dictionary, default, *keys):
    nested_dictionary = dictionary
    for key in keys:
        try:
            nested_dictionary = nested_dictionary[key]
        except KeyError:
            return default
    return nested_dictionary

def dict_nested_set(dictionary, value, *keys):
    nested_dictionary = dictionary
    for key in keys[:-1]:
        try:
            nested_dictionary = nested_dictionary[key]
        except KeyError:
            nested_dictionary[key] = {}
            nested_dictionary = nested_dictionary[key]
    nested_dictionary[keys[-1]] = value

class Asset:
    _asset_id: int
    
    _algod: AlgodClient
    _assets: Assets
    
    _name: str
    _price_source: str
    _amount: int
    _price: float
    _decimals: int
    
    _creator: str
    _asset_info: dict
    _creator_account_info: dict
    
    def __init__(self, asset_id: int, algod: AlgodClient, assets: Assets, asset_config: dict) -> None:
        self._asset_id = asset_id
        self._algod = algod
        self._assets = assets
        self._name = asset_config.get('name', None)
        self._price_source = asset_config.get('price_source', None)
        self._amount = asset_config.get('amount', 0)
        self._price = asset_config.get('price', None)
        self._decimals = asset_config.get('decimals', None)
    
    def get_id(self) -> int:
        return self._asset_id
    
    def get_name(self) -> str:
        if self._name == None:
            if self._asset_id == 0:
                self._name = 'Algo'
            else:
                cache = self._load_cache()
                cached_asset_name = dict_nested_get(cache, None, 'assets', str(self._asset_id), 'name')
                if cached_asset_name == None:
                    cached_asset_name = dict_nested_get(self._get_asset_info(), '', 'params', 'name')
                    dict_nested_set(cache, cached_asset_name, 'assets', str(self._asset_id), 'name')
                    self._save_cache(cache)
                self._name = cached_asset_name
        return self._name
    
    def get_decimals(self) -> int:
        if self._decimals == None:
            if self._asset_id == 0:
                self._decimals = 6
            else:
                cache = self._load_cache()
                cached_decimals = dict_nested_get(cache, None, 'assets', str(self._asset_id), 'decimals')
                if cached_decimals == None:
                    cached_decimals = dict_nested_get(self._get_asset_info(), '', 'params', 'decimals')
                    dict_nested_set(cache, cached_decimals, 'assets', str(self._asset_id), 'decimals')
                    self._save_cache(cache)
                self._decimals = cached_decimals
        return self._decimals
    
    def get_price_source(self) -> str:
        if self._price_source == None:
            if self._asset_id == 0:
                self._price_source = 'N/A'
            else:
                if self.get_name().startswith('Tinyman Pool '):
                    self._price_source = 'Tinyman Pool Token'
                else:
                    self._price_source = 'Tinyman'
        return self._price_source
    
    def get_amount(self) -> int:
        return self._amount
    
    def add_amount(self, increment: int) -> None:
        self._amount = self.get_amount() + increment
    
    def get_price(self) -> float:
        if self._price == None:
            if self._asset_id == 0:
                self._price = 1
            else:
                if self.get_price_source() == 'Tinyman':
                    tinyman_client = TinymanMainnetClient()
                    tinyman_algo = tinyman_client.fetch_asset(0)
                    tinyman_asset = tinyman_client.fetch_asset(self._asset_id)
                    tinyman_pool = tinyman_client.fetch_pool(tinyman_asset, tinyman_algo)
                    try:
                        quote = tinyman_pool.fetch_fixed_input_swap_quote(tinyman_asset(1_000_000), slippage=0.01)
                    except Exception:
                        self._price = None
                    else:
                        self._price = quote.price
                elif self.get_price_source() == 'Tinyman Pool Token':
                    pool_info = get_pool_info_from_account_info(self._get_creator_account_info())
                    price_asset1 = self._assets.get(pool_info['asset1_id']).get_price()
                    total_value_asset1 = price_asset1 * pool_info['asset1_reserves']
                    price_asset2 = self._assets.get(pool_info['asset2_id']).get_price()
                    total_value_asset2 = price_asset2 * pool_info['asset2_reserves']
                    self._price = (total_value_asset1 + total_value_asset2) / pool_info['issued_liquidity']
                else:
                    self._price = None
        return self._price
    
    def get_value(self) -> float:
        price = self.get_price()
        if price == None:
            return None
        else:
            return self.get_amount() * price
    
    def _get_creator(self) -> str:
        if not hasattr(self, '_creator'):
            cache = self._load_cache()
            cached_creator = dict_nested_get(cache, None, 'assets', str(self._asset_id), 'creator')
            if cached_creator == None:
                cached_creator = dict_nested_get(self._get_asset_info(), '', 'params', 'creator')
                dict_nested_set(cache, cached_creator, 'assets', str(self._asset_id), 'creator')
                self._save_cache(cache)
            self._creator = cached_creator
        return self._creator
    
    def _get_asset_info(self) -> dict:
        if not hasattr(self, '_asset_info'):
            self._asset_info = self._algod.asset_info(self._asset_id)
        return self._asset_info
    
    def _get_creator_account_info(self) -> dict:
        if not hasattr(self, '_creator_account_info'):
            self._creator_account_info = self._algod.account_info(self._get_creator())
        return self._creator_account_info
    
    def _load_cache(self) -> dict:
        if os.path.isfile('Cache.json'):
            with open("Cache.json", "r") as stream:
                return json.load(stream)
        else:
            return {}

    def _save_cache(self, cache):
        with open("Cache.json", "w") as stream:
            json.dump(cache, stream)

class Assets:
    _assets: dict
    _assets_config: dict
    _algod: AlgodClient
    
    def __init__(self, assets_config: dict, algod: AlgodClient) -> None:
        self._assets = {}
        self._assets_config = assets_config
        self._algod = algod
    
    def get(self, asset_id) -> Asset:
        if asset_id not in self._assets:
            self._assets[asset_id] = Asset(asset_id, self._algod, self, self._assets_config.get(asset_id, {}))
        return self._assets[asset_id]
    
    def add_wallets(self, wallets: list) -> None:
        for wallet in wallets:
            account_info = self._algod.account_info(wallet)
            self.get(0).add_amount(account_info['amount'])
            for account_info_asset in account_info['assets']:
                self.get(account_info_asset['asset-id']).add_amount(account_info_asset['amount'])
    
    def get_asset_ids(self) -> list:
        return list(self._assets.keys())

def load():
    if os.path.isfile('Config.yaml'):
        with open("Config.yaml", "r") as stream:
            return yaml.safe_load(stream)
    else:
        return {}

def create_wallets_table(wallets):
    if len(wallets) == 0:
        print("No wallets")
        return
    wallets_sheet = ipysheet.sheet(key='wallets', rows=len(wallets), columns=1, column_headers=['Public Key'])
    for i in range(len(wallets)):
        ipysheet.cell(i, 0, value=wallets[i], type='text', read_only=True)
    display(wallets_sheet)

def create_assets_table(assets, display_asset_id=0):
    asset_ids = list(filter(lambda asset_id: assets.get(asset_id).get_amount() != 0, assets.get_asset_ids()))
    if len(asset_ids) == 0:
        print("No assets")
        return
    assets_sheet = ipysheet.sheet(key='assets', rows=len(asset_ids), columns=6, column_headers=['Name', 'ID', 'Price Source', 'Amount', 'Price', 'Value'])
    i = 0
    total_value = 0
    display_asset_price = assets.get(display_asset_id).get_price()
    display_asset_decimals_factor = math.pow(10, assets.get(display_asset_id).get_decimals())
    for asset_id in asset_ids:
        asset = assets.get(asset_id)
        ipysheet.cell(i, 0, value=asset.get_name(), read_only=True)
        ipysheet.cell(i, 1, value=str(asset.get_id()), read_only=True)
        ipysheet.cell(i, 2, value=asset.get_price_source(), read_only=True)
        asset_decimals_factor = math.pow(10, asset.get_decimals())
        ipysheet.cell(i, 3, value=str(asset.get_amount() / asset_decimals_factor), read_only=True)
        if asset.get_price() == None:
            priceStr = 'Error'
        else:
            priceStr = str(asset.get_price() / display_asset_price * asset_decimals_factor / display_asset_decimals_factor)
        ipysheet.cell(i, 4, value=priceStr, read_only=True)
        if asset.get_value() == None:
            valueStr = 'Error'
        else:
            valueStr = str(asset.get_value() / display_asset_price / display_asset_decimals_factor)
            total_value += asset.get_value()
        ipysheet.cell(i, 5, value=valueStr, read_only=True)
        i = i + 1
    print("Total value: {}".format(total_value / display_asset_price / display_asset_decimals_factor))
    display(assets_sheet)

def fill_assets(config):
    algod_client = AlgodClient("", "https://api.algoexplorer.io", headers={'User-Agent': 'algosdk'})
    assets = Assets(config.get('assets', {}), algod_client)
    assets.add_wallets(config.get('wallets', []))
    return assets
