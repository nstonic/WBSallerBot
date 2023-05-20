import os
import pathlib
from base64 import b64decode
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from reportlab.graphics.barcode import code128
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, NextPageTemplate
from reportlab.platypus import Image, Frame, PageBreak
from reportlab.platypus.para import Paragraph
from reportlab.platypus.tables import Table

import config
from wb_api.classes import Order, Product, OrderQRCode, SupplySticker


def create_supply_sticker(supply_sticker: SupplySticker) -> bytes:
    sticker_in_byte_format = b64decode(
        supply_sticker.image_string,
        validate=True
    )
    image = Image.open(
        BytesIO(
            sticker_in_byte_format
        )
    ).rotate(-90, expand=True)
    image_to_sending = BytesIO()
    image.save(image_to_sending, format='PNG')
    return image_to_sending.getvalue()


def get_orders_stickers(
        orders: list[Order],
        products: list[Product],
        qr_codes: list[OrderQRCode],
        supply_id: str
) -> BytesIO:
    articles = set([order.article for order in orders])
    sticker_files = []
    for article in articles:
        orders_with_same_article = list(filter(
            lambda o: o.article == article,
            orders
        ))
        product = next(filter(
            lambda p: p.article == article,
            products
        ))
        sticker_file = create_stickers_for_order(
            orders_with_same_article,
            product,
            qr_codes
        )
        sticker_files.append(sticker_file)

    zip_file = BytesIO()
    zip_file.name = f'Stickers for {supply_id}.zip'
    with ZipFile(zip_file, 'a', ZIP_DEFLATED, False) as archive:
        for sticker_file in sticker_files:
            archive.writestr(sticker_file.name, sticker_file.getvalue())
    return zip_file


def create_stickers_for_order(
        orders: list[Order],
        product: Product,
        qr_codes: list[OrderQRCode]
) -> BytesIO:
    order_qr_code_files = []
    for order in orders:
        order_qr_code = next(filter(
            lambda qr: qr.order_id == order.order_id,
            qr_codes
        ))
        sticker_in_byte_format = b64decode(
            order_qr_code.file,
            validate=True
        )
        order_qr_code_files.append(
            BytesIO(sticker_in_byte_format)
        )
    return build_pdf_with_stickers_for_order(
        product,
        order_qr_code_files
    )


def build_pdf_with_stickers_for_order(
        product: Product,
        order_qr_code_files:
        list[BytesIO]
) -> BytesIO:
    pdf_file = BytesIO()
    pdf_file.name = f'{product.article}.pdf'

    font_path = os.path.join(pathlib.Path(__file__).parent.resolve(), config.FONT_FILE)
    pdfmetrics.registerFont(TTFont(config.FONT_NAME, font_path))
    sticker_size = (120 * mm, 75 * mm)
    pdf = BaseDocTemplate(pdf_file, showBoundary=0)
    style = getSampleStyleSheet()['BodyText']
    style.fontName = config.FONT_NAME
    frame_sticker = Frame(0, 0, *sticker_size)
    frame_description = Frame(10 * mm, 5 * mm, 100 * mm, 40 * mm)

    elements = []
    for sticker in order_qr_code_files:
        data = [
            [Paragraph(product.name, style)],
            [Paragraph(f'Артикул: {product.article}', style)],
            [Paragraph(f'Страна: {config.COUNTRY}', style)],
            [Paragraph(f'Бренд: {config.BRAND}', style)]
        ]

        elements.append(Image(sticker, useDPI=300, width=95 * mm, height=65 * mm))
        elements.append(NextPageTemplate('Barcode'))
        elements.append(PageBreak())
        elements.append(Table(data, colWidths=[100 * mm]))
        elements.append(NextPageTemplate('Image'))
        elements.append(PageBreak())

        def barcode(canvas, doc):
            canvas.saveState()
            barcode128 = code128.Code128(
                product.barcode,
                barHeight=50,
                barWidth=1.45,
                humanReadable=True
            )
            barcode128.drawOn(canvas, x=19.5 * mm, y=53 * mm)
            canvas.restoreState()

        pdf.addPageTemplates(
            [PageTemplate(id='Image', frames=frame_sticker, pagesize=sticker_size),
             PageTemplate(id='Barcode', frames=frame_description, pagesize=sticker_size, onPage=barcode)]
        )
    pdf.build(elements)
    return pdf_file
