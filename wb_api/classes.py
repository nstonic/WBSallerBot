import datetime
from dataclasses import dataclass

from pydantic import BaseModel, Field

from utils import convert_to_created_ago


class ButtonMixin:
    def get_callback_data(self):
        return self.id

    def get_button_text(self):
        return self.__str__()


class Supply(BaseModel, ButtonMixin):
    id: str
    name: str
    closed_at: datetime.datetime = Field(alias='closedAt', default=None)
    created_at: datetime.datetime = Field(alias='createdAt')
    is_done: bool = Field(alias='done')

    def to_tuple(self):
        return self.id, self.name, self.closed_at, self.created_at, self.is_done

    def get_button_text(self):
        is_done = {0: 'Открыта', 1: 'Закрыта'}
        return f'{self.name} | {self.id} | {is_done[self.is_done]}'


class Order(BaseModel, ButtonMixin):
    id: int
    supply_id: str = Field(alias='supplyId', default='Не закреплён за поставкой')
    converted_price: int = Field(alias='convertedPrice')
    article: str
    created_at: datetime.datetime = Field(alias='createdAt')

    def get_callback_data(self):
        return self.id

    def get_button_text(self):
        return f'{self.article} | {convert_to_created_ago(self.created_at)}'


class OrderQRCode(BaseModel):
    order_id: int = Field(alias='orderId')
    file: str
    partA: str
    partB: str


class SupplyQRCode(BaseModel):
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
