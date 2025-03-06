from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.add_font('DejaVu', '', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf', uni=True)
pdf.set_font('DejaVu', size=14)

text = """Политика конфиденциальности

1. Мы собираем только необходимые данные для работы сервиса
2. Ваши данные защищены
3. Мы не передаем данные третьим лицам"""

pdf.multi_cell(0, 10, text)
pdf.output("privacy_policy.pdf") 