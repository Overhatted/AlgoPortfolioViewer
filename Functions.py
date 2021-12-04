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
    total_value = 0
    for i in range(len(config['assets'])):
        ipysheet.cell(i, 0, value=config['assets'][i]['name'], type='text', read_only=True)
        ipysheet.cell(i, 1, value=config['assets'][i]['id'], type='text', read_only=True)
        ipysheet.cell(i, 2, value=config['assets'][i]['type'], type='text', read_only=True)
        ipysheet.cell(i, 3, value=config['assets'][i]['amount'], type='numeric', read_only=True)
        ipysheet.cell(i, 4, value=config['assets'][i]['price'], type='numeric', read_only=True)
        ipysheet.cell(i, 5, value=config['assets'][i]['value'], type='numeric', read_only=True)
        total_value = total_value + config['assets'][i]['value']
    print("Total value: {}".format(total_value))
    display(assets_sheet)

def add_asset_amount(config, wallet, asset_id, asset_amount):
    assets_with_this_id = list(filter(lambda asset: asset['id'] == asset_id, config['assets']))
    if len(assets_with_this_id) == 0:
        print("Asset with id {} not found. Is in wallet {}".format(asset_id, wallet))
    else:
        assets_with_this_id[0]['amount'] = assets_with_this_id[0]['amount'] + asset_amount / 1_000_000

def fill_assets_amount(config):
    if "algod" not in config:
        config['algod'] = AlgodClient("", "https://api.algoexplorer.io", headers={'User-Agent': 'algosdk'})
    
    for asset in config['assets']:
        asset['amount'] = 0
    
    for wallet in config['wallets']:
        account_info = config['algod'].account_info(wallet)
        print(account_info)
        add_asset_amount(config, wallet, 0, account_info['amount'])
        for account_info_asset in account_info['assets']:
            add_asset_amount(config, wallet, account_info_asset['asset-id'], account_info_asset['amount'])

def fill_assets_price(config):
    tinyman_client = TinymanMainnetClient()
    tinyman_algo = tinyman_client.fetch_asset(0)

    for asset in config['assets']:
        if int(asset['id']) == 0:
            asset['price'] = 1
        else:
            asset['tinyman_asset'] = tinyman_client.fetch_asset(int(asset['id']))
            asset['tinyman_pool'] = tinyman_client.fetch_pool(asset['tinyman_asset'], tinyman_algo)
            quote = asset['tinyman_pool'].fetch_fixed_input_swap_quote(asset['tinyman_asset'](1_000_000), slippage=0.01)
            asset['price'] = quote.price

def fill_assets_value(config):
    for asset in config['assets']:
        asset['value'] = asset['amount'] * asset['price']

def fill_assets(config):
    fill_assets_amount(config)
    fill_assets_price(config)
    fill_assets_value(config)