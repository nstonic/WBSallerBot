import datetime
from dataclasses import dataclass
from pprint import pprint

import requests
from pydantic import BaseModel, Field

from wb_api.errors import retry_on_network_error, check_response


class Supply(BaseModel):
    id: str
    name: str
    closed_at: datetime.datetime = Field(alias='closedAt', default=None)
    created_at: datetime.datetime = Field(alias='createdAt')
    is_done: bool = Field(alias='done')


class Order(BaseModel):
    id: int
    supply_id: str = Field(alias='supplyId', default='')
    converted_price: int = Field(alias='convertedPrice')
    article: str
    created_at: datetime.datetime = Field(alias='createdAt')


class OrderQRCode(BaseModel):
    order_id: int = Field(alias='orderId')
    file: str
    part_a: str = Field(alias='partA')
    part_b: str = Field(alias='partB')


class SupplyQRCode(BaseModel):
    barcode: str
    image_string: str = Field(alias='file')


@dataclass
class Product:
    article: str
    name: str = ''
    barcode: str = ''
    brand: str = ''
    countries: list[str] = tuple()
    colors: list[str] = tuple()
    media_urls: list[str] = tuple()
    media_files: list[bytes] = tuple()

    @staticmethod
    def parse_from_card(product_card: dict):
        characteristics = {
            key: value
            for characteristic in product_card.get('characteristics')
            for key, value in characteristic.items()
        }
        size, *_ = product_card.get('sizes')
        barcode, *_ = size.get('skus', '')
        return Product(
            article=product_card.get('vendorCode', ''),
            name=characteristics.get('Наименование', ''),
            brand=characteristics.get('Бренд', ''),
            barcode=barcode,
            colors=characteristics.get('Цвет', []),
            countries=characteristics.get('Страна производства', []),
            media_files=product_card.get('mediaFiles', [])
        )

    @retry_on_network_error
    def get_media(self):
        for media_file in self.media_urls:
            response = requests.get(media_file)
            check_response(response)
            self.media_files.append(response.content)
