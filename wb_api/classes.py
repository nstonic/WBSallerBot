import datetime
from dataclasses import dataclass

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
    name: str = None
    barcode: str = None
    media_urls: list[str] = None
    media_files: list[bytes] = None

    @staticmethod
    def parse_from_card(product_card: dict):
        for characteristic in product_card.get('characteristics'):
            if name := characteristic.get('Наименование'):
                break
        else:
            name = 'Наименование продукции'
        barcode = product_card['sizes'][0]['skus'][0]
        article = product_card.get('vendorCode', '0000000000')
        media_files = product_card.get('mediaFiles')
        return Product(
            article=article,
            name=name,
            barcode=barcode,
            media_files=media_files
        )

    @retry_on_network_error
    def get_media(self):
        for media_file in self.media_urls:
            response = requests.get(media_file)
            check_response(response)
            self.media_files.append(response.content)
