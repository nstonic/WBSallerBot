from typing import Iterable, Generator

import more_itertools
import requests

from .classes import Supply, Order, Product, Sticker, SupplySticker
from .errors import check_response, retry_on_network_error, WBAPIError


class WBApiClient:
    instance = None

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, **kwargs):
        if kwargs:
            self._headers = {'Authorization': kwargs['token']}

    @retry_on_network_error
    def get_orders(self, supply_id: str) -> list[Order]:
        response = requests.get(
            f'https://suppliers-api.wildberries.ru/api/v3/supplies/{supply_id}/orders',
            headers=self._headers
        )
        check_response(response)
        return [Order.parse_obj(order) for order in response.json()['orders']]

    @retry_on_network_error
    def get_product(self, article: str) -> Product:
        response = requests.post(
            'https://suppliers-api.wildberries.ru/content/v1/cards/filter',
            json={'vendorCodes': [article]},
            headers=self._headers
        )
        check_response(response)
        for product_card in response.json()["data"]:
            if product_card["vendorCode"] == article:
                return Product.parse_from_card(product_card)
        return Product(article=article)

    @retry_on_network_error
    def get_all_products(self) -> Generator:
        cursor = {
            'limit': 1000
        }
        while True:
            response = requests.post(
                'https://suppliers-api.wildberries.ru/content/v1/cards/cursor/list',
                headers=self._headers,
                json={
                    'sort': {
                        'cursor': cursor,
                        'filter': {'withPhoto': -1}
                    }
                }

            )
            check_response(response)
            response_data = response.json()['data']
            product_cards = response_data['cards']
            cursor.update({
                'nmID': response_data['cursor']['nmID'],
                'updatedAt': response_data['cursor']['updatedAt']
            })
            for product_card in product_cards:
                yield product_card

            if response_data['cursor']['total'] < cursor['limit']:
                break
            else:
                continue

    @retry_on_network_error
    def get_all_product_cards(self, articles: Iterable) -> Generator:
        for chunk in more_itertools.chunked(articles, 100):
            response = requests.post(
                'https://suppliers-api.wildberries.ru/content/v1/cards/filter',
                json={'vendorCodes': chunk},
                headers=self._headers
            )
            check_response(response)
            for product_card in response.json()['data']:
                yield product_card

    @retry_on_network_error
    def get_supplies(self, only_active: bool = True, limit: int = 50) -> list[Supply]:
        params = {
            'limit': 1000,
            'next': 0
        }

        while True:  # Находим последнюю страницу с поставками
            response = requests.get(
                'https://suppliers-api.wildberries.ru/api/v3/supplies',
                headers=self._headers,
                params=params
            )
            check_response(response)
            if response.json()['supplies'] == params['limit']:
                params['next'] = response.json()['next']
                continue
            else:
                break

        supplies = []
        for supply in response.json()["supplies"][::-1]:
            if not supply['done'] or only_active is False:
                supply = Supply.parse_obj(supply)
                supplies.append(supply)
            if len(supplies) == limit:
                break
        return supplies

    @retry_on_network_error
    def get_stickers(self, order_ids: list[int]) -> list[Sticker]:
        stickers = list()
        for chunk in more_itertools.chunked(order_ids, 100):
            response = requests.post(
                'https://suppliers-api.wildberries.ru/api/v3/orders/stickers',
                headers=self._headers,
                json={'orders': chunk},
                params={
                    'type': 'png',
                    'width': 58,
                    'height': 40
                }
            )
            check_response(response)
            stickers.extend([Sticker.parse_obj(sticker) for sticker in response.json()['stickers']])
        return stickers

    @retry_on_network_error
    def send_supply_to_deliver(self, supply_id: str) -> int:
        response = requests.patch(
            f'https://suppliers-api.wildberries.ru/api/v3/supplies/{supply_id}/deliver',
            headers=self._headers
        )
        response.raise_for_status()
        return response.status_code

    @retry_on_network_error
    def get_supply_sticker(self, supply_id: str) -> SupplySticker:
        response = requests.get(
            f'https://suppliers-api.wildberries.ru/api/v3/supplies/{supply_id}/barcode',
            headers=self._headers,
            params={
                'type': 'png',
                'width': 58,
                'height': 40
            }
        )
        check_response(response)
        return SupplySticker.parse_obj(response.json())

    @retry_on_network_error
    def get_new_orders(self) -> Generator:
        response = requests.get(
            f'https://suppliers-api.wildberries.ru/api/v3/orders/new',
            headers=self._headers
        )
        check_response(response)
        return (Order.parse_obj(order) for order in response.json()['orders'])

    @retry_on_network_error
    def add_order_to_supply(self, supply_id: str, order_id: int | str) -> int:
        response = requests.patch(
            f'https://suppliers-api.wildberries.ru/api/v3/supplies/{supply_id}/orders/{order_id}',
            headers=self._headers
        )
        if status_code := response.status_code != 204:
            raise (WBAPIError(f'Статус запроса: {status_code}'))
        response.raise_for_status()
        return response.status_code

    @retry_on_network_error
    def create_new_supply(self, supply_name: str) -> str:
        response = requests.post(
            f'https://suppliers-api.wildberries.ru/api/v3/supplies',
            headers=self._headers,
            json={'name': supply_name}
        )
        check_response(response)
        return response.json()['id']

    @retry_on_network_error
    def delete_supply_by_id(self, supply_id: str) -> int:
        response = requests.delete(
            f'https://suppliers-api.wildberries.ru/api/v3/supplies/{supply_id}',
            headers=self._headers
        )
        response.raise_for_status()
        return response.status_code
