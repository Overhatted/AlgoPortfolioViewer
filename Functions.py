import os, yaml, ipysheet
from algosdk.v2client.algod import AlgodClient
from tinyman.v1.client import TinymanMainnetClient

def load():
    if os.path.isfile('Config.yaml'):
        with open("Config.yaml", "r") as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
                exit()
    else:
        return {'wallets': [], 'assets': []}

def create_wallets_table(config):
    if len(config['wallets']) == 0:
        print("No wallets")
        return
    wallets_sheet = ipysheet.sheet(key='wallets', rows=len(config['wallets']), columns=1, column_headers=['Public Key'])
    for i in range(len(config['wallets'])):
        ipysheet.cell(i, 0, value=config['wallets'][i], type='text', read_only=True)
    display(wallets_sheet)

def create_assets_table(config):
    if len(config['assets']) == 0:
        print("No assets")
        return
    assets_sheet = ipysheet.sheet(key='assets', rows=len(config['assets']), columns=6, column_headers=['Name', 'ID', 'Type', 'Amount', 'Price', 'Value'])
    i = 0
    total_value = 0
    for asset_id, asset in config['assets'].items():
        ipysheet.cell(i, 0, value=asset['name'], read_only=True)
        ipysheet.cell(i, 1, value=str(asset_id), read_only=True)
        ipysheet.cell(i, 2, value=asset['type'], read_only=True)
        ipysheet.cell(i, 3, value=str(asset['amount']), read_only=True)
        ipysheet.cell(i, 4, value=str(asset['price']), read_only=True)
        ipysheet.cell(i, 5, value=str(asset['value']), read_only=True)
        total_value = total_value + asset['value']
        i = i + 1
    print("Total value: {}".format(total_value))
    display(assets_sheet)

def add_algod_client(config):
    if "algod" not in config:
        config['algod'] = AlgodClient("", "https://api.algoexplorer.io", headers={'User-Agent': 'algosdk'})

def add_asset_amount(config, wallet, asset_id, asset_amount):
    if asset_id in config['assets']:
        if 'amount' in config['assets'][asset_id]:
            config['assets'][asset_id]['amount'] += asset_amount / 1_000_000
        else:
            config['assets'][asset_id]['amount'] = asset_amount / 1_000_000
    else:
        config['assets'][asset_id] = {'amount': asset_amount / 1_000_000}

def fill_assets_amount(config):
    for wallet in config['wallets']:
        account_info = config['algod'].account_info(wallet)
        add_asset_amount(config, wallet, 0, account_info['amount'])
        for account_info_asset in account_info['assets']:
            add_asset_amount(config, wallet, account_info_asset['asset-id'], account_info_asset['amount'])

def fill_missing_asset_info(config):
    for asset_id, asset in config['assets'].items():
        if 'name' not in asset:
            asset['name'] = ''
        if 'type' not in asset:
            if asset_id == 0:
                asset['type'] = 'N/A'
            else:
                asset['type'] = 'Tinyman'
        if 'amount' not in asset:
            asset['amount'] = 0

def fill_assets_price(config):
    tinyman_client = TinymanMainnetClient()
    tinyman_algo = tinyman_client.fetch_asset(0)
    
    for asset_id, asset in config['assets'].items():
        if 'price' in asset:
            continue
        if asset['amount'] == 0:
            asset['price'] = '?'
            continue
        if asset_id == 0:
            asset['price'] = 1
            continue

        if asset['type'] == 'Tinyman':
            asset['tinyman_asset'] = tinyman_client.fetch_asset(asset_id)
            asset['tinyman_pool'] = tinyman_client.fetch_pool(asset['tinyman_asset'], tinyman_algo)
            try:
                quote = asset['tinyman_pool'].fetch_fixed_input_swap_quote(asset['tinyman_asset'](1_000_000), slippage=0.01)
            except Exception:
                asset['price'] = 'Error'
            else:
                asset['price'] = quote.price
        else:
            asset['price'] = 'Unknown type'

def fill_assets_value(config):
    for asset_id, asset in config['assets'].items():
        try:
            priceInt = float(asset['price'])
        except ValueError:
            asset['value'] = 0
        else:
            asset['value'] = asset['amount'] * priceInt

def fill_assets(config):
    add_algod_client(config)
    fill_assets_amount(config)
    fill_missing_asset_info(config)
    fill_assets_price(config)
    fill_assets_value(config)
