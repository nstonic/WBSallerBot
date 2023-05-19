import datetime
from dataclasses import dataclass

from pydantic import BaseModel, Field


class Supply(BaseModel):
    supply_id: str = Field(alias='id')
    name: str
    closed_at: datetime.datetime = Field(alias='closedAt', default=None)
    created_at: datetime.datetime = Field(alias='createdAt')
    is_done: bool = Field(alias='done')

    def to_tuple(self):
        return self.supply_id, self.name, self.closed_at, self.created_at, self.is_done


class Order(BaseModel):
    order_id: int = Field(alias='id')
    supply_id: str = Field(alias='supplyId', default='Не закреплён за поставкой')
    converted_price: int = Field(alias='convertedPrice')
    article: str
    created_at: datetime.datetime = Field(alias='createdAt')


class OrderQRCode(BaseModel):
    order_id: int = Field(alias='orderId')
    file: str
    partA: str
    partB: str


class SupplySticker(BaseModel):
    barcode: str
    image_string: str = Field(alias='file')


@dataclass
class Product:
    article: str
    name: str = None
    barcode: str = None

    def to_tuple(self):
        return self.article, self.name, self.barcode

    @staticmethod
    def parse_from_card(product_card: dict):
        for characteristic in product_card.get('characteristics'):
            if name := characteristic.get('Наименование'):
                break
        else:
            name = 'Наименование продукции'
        barcode = product_card['sizes'][0]['skus'][0]
        article = product_card.get('vendorCode', '0000000000')
        return Product(
            name=name,
            barcode=barcode,
            article=article
        )
