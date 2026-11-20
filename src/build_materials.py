"""Generate editable PowerPoint, Word report, and speaker cue sheet from analysis outputs.
If real analysis is absent, empirical slides explicitly say 'not yet calculated'.
"""
from __future__ import annotations
import argparse,json,sys,math
from pathlib import Path
import pandas as pd
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN,MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from docx import Document
from docx.shared import Cm,Pt as DPt,RGBColor as DRGB
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

ROOT=Path(__file__).resolve().parents[1]
O=ROOT/'presentation';D=ROOT/'docs'
O.mkdir(exist_ok=True);D.mkdir(exist_ok=True)
NAVY='0B1426';PANEL='16243A';PANEL2='1D3049';WHITE='F5F9FE';MUTED='B4C3D3';CYAN='2FD0C4';GOLD='F5C26C';RED='FF7183'

def rgb(h):return RGBColor.from_string(h)

def rect(sl,x,y,w,h,color,rad=False):
    obj=sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rad else MSO_SHAPE.RECTANGLE, Inches(x),Inches(y),Inches(w),Inches(h))
    obj.fill.solid();obj.fill.fore_color.rgb=rgb(color);obj.line.fill.background();return obj

def text(sl,x,y,w,h,s,size=18,color=WHITE,bold=False,align=None,font='Aptos',margin=.05):
    sh=sl.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=sh.text_frame;tf.clear();tf.word_wrap=True
    tf.margin_left=tf.margin_right=Inches(margin);tf.margin_top=tf.margin_bottom=Inches(margin)
    lines=str(s).split('\n')
    for idx,line in enumerate(lines):
        p=tf.paragraphs[0] if idx==0 else tf.add_paragraph()
        p.text=line;p.font.size=Pt(size);p.font.name=font;p.font.bold=bold;p.font.color.rgb=rgb(color)
        p.space_after=Pt(8 if idx<len(lines)-1 else 0)
        if align is not None:p.alignment=align
    return sh

def base(prs,title,sub=None,idx=None,tag=None):
    sl=prs.slides.add_slide(prs.slide_layouts[6])
    sl.background.fill.solid();sl.background.fill.fore_color.rgb=rgb(NAVY)
    rect(sl,.42,.57,.08,.72,CYAN)
    text(sl,.67,.38,11.7,.3,'АДиМО  /  ПРАКТИКИ 11–12  /  КОМАНДА № 3',10,CYAN,True)
    # One-line heading area: never overlap the subtitle on long Russian titles.
    title_size = 30 if len(title) < 49 else (26 if len(title) < 60 else 23)
    text(sl,.66,.91,12.05,.59,title,title_size,WHITE,True)
    if sub:text(sl,.68,1.64,12.0,.40,sub,14,MUTED)
    rect(sl,.68,7.1,11.95,.015,'24384D')
    text(sl,.69,7.16,8.2,.16,'Демографическая структура регионов • 2021',9,MUTED)
    if idx is not None:text(sl,12.05,7.13,.35,.22,f'{idx:02d}',10,CYAN,True,PP_ALIGN.RIGHT)
    if tag:text(sl,8.1,7.12,3.65,.2,tag,8,GOLD,True,PP_ALIGN.RIGHT)
    return sl

def card(sl,x,y,w,h,title,body,accent=CYAN,body_size=17):
    rect(sl,x,y,w,h,PANEL,True)
    rect(sl,x+.17,y+.24,.055,.43,accent)
    text(sl,x+.35,y+.19,w-.55,.48,title,18,WHITE,True)
    text(sl,x+.33,y+.78,w-.62,h-.9,body,body_size,MUTED)

def picture(sl,p,x,y,w,h):
    if p and Path(p).exists():
        from PIL import Image
        im=Image.open(p)
        rw,rh=im.size;aspect=rw/rh; frame=w/h
        # Contain image without cropping; on panels use light background.
        rect(sl,x,y,w,h,'EFF4F8',True)
        # Add a safety inset so picture corners stay inside the rounded panel.
        inset = .075
        x+=inset; y+=inset; w-=2*inset; h-=2*inset
        frame=w/h
        if aspect>frame:
            iw=w;ih=w/aspect;ix=x;iy=y+(h-ih)/2
        else:
            ih=h;iw=h*aspect;ix=x+(w-iw)/2;iy=y
        sl.shapes.add_picture(str(p),Inches(ix),Inches(iy),width=Inches(iw),height=Inches(ih))
    else:
        rect(sl,x,y,w,h,PANEL,True)
        text(sl,x+.35,y+.35,w-.7,h-.7,'Карта и числовые результаты появятся после запуска проекта на исходных данных 2021 года.',17,MUTED,False,PP_ALIGN.CENTER)

def make_ppt(summary,out,maps,demo=False):
    """Self-contained, legible slides. Every graph states variable, units, and interpretation."""
    r=Presentation();r.slide_width=Inches(13.333);r.slide_height=Inches(7.5)
    active=bool(summary) and summary.get('status')=='completed_2021_data'
    has_results=bool(summary) and (active or demo)
    status=('ДЕМОНСТРАЦИЯ НА ВЫМЫШЛЕННЫХ ДАННЫХ' if demo else
            ('ФАКТИЧЕСКИЕ ДАННЫЕ 2021' if active else 'ШАБЛОН ДО ЗАГРУЗКИ ДАННЫХ'))
    def slide(title,sub,idx):
        return base(r,title,sub,idx,status)
    def note(sl,s,accent=GOLD,y=6.77):
        text(sl,.85,y,11.75,.29,s,13,accent,False)
    def chart_slide(title,sub,idx,path,explain):
        sl=slide(title,sub,idx)
        picture(sl,(maps/path) if has_results else None,.51,1.99,12.30,4.64)
        note(sl,explain,y=6.70)
        return sl

    sl=slide('Демографическое сходство регионов','Пространственная кластеризация субъектов РФ • показатели 2021 года',1)
    rect(sl,.72,2.30,11.88,3.75,PANEL,True)
    text(sl,1.20,2.66,10.7,1.35,'Какие регионы похожи\nпо демографической ситуации?',33,WHITE,True)
    text(sl,1.22,4.68,10.6,.58,'Четыре показателя   ·   три алгоритма   ·   проверка географии и устойчивости',18,CYAN)
    text(sl,1.22,5.63,10.6,.28,'Команда № 3  /  АДиМО  /  Семинар-защита • 10 минут',13,MUTED)

    sl=slide('Мы ищем не «лучшие» регионы, а похожие','Задача: выделить группы территорий по нескольким демографическим характеристикам',2)
    metrics=[('Доля горожан','%', 'Какая часть населения живёт в городах'),
             ('Естественный прирост','‰','Разница рождений и смертей на 1000 жителей'),
             ('Миграционный прирост','‰','Приехавшие минус выбывшие на 1000 жителей'),
             ('Суммарная рождаемость','детей', 'Ожидаемое число рождений на одну женщину')]
    for i,(title,unit,meaning) in enumerate(metrics):
        xx=.8+(i%2)*6.03; yy=2.16+(i//2)*2.14
        rect(sl,xx,yy,5.7,1.90,PANEL,True)
        text(sl,xx+.27,yy+.18,4.8,.38,title,20,WHITE,True)
        text(sl,xx+.25,yy+.64,5.05,.73,meaning,16,MUTED)
        text(sl,xx+.27,yy+1.53,4.9,.20,'Единица: '+unit,11,CYAN,True)
    note(sl,'Принцип: близкие значения всех четырёх показателей → одна демографическая группа.')

    sl=slide('Сначала соединяем таблицу с географией','Ошибочное сопоставление названий делает даже красивую карту неверной',3)
    steps=[('01','4 показателя','Росстат / «Если быть точным», 2021'),
           ('02','Коды и названия','Без РФ целиком и федеральных округов'),
           ('03','Границы субъектов','Открытый GeoJSON, WGS84'),
           ('04','Проверки','Пропуски, дубли, геометрии, соответствие')]
    for i,(num,title,detail) in enumerate(steps):
        yy=2.04+i*1.09
        rect(sl,.82,yy,11.66,.94,PANEL,True)
        text(sl,1.05,yy+.16,.7,.42,num,19,CYAN,True)
        text(sl,1.94,yy+.13,3.30,.41,title,20,WHITE,True)
        text(sl,5.08,yy+.16,7.0,.43,detail,15,MUTED)
    note(sl,'Правило: сомнительные совпадения не соединяются автоматически; исключения заносятся в журнал.',y=6.69)

    names=[('urban_share.png','Где выше доля городского населения?',
            'Шкала: фиолетовый — ниже, жёлтый — выше. Доля населения в городах, %.'),
           ('natural_change.png','Где выше естественный прирост?',
            'Положительное значение означает превышение числа рождений над числом смертей. Единица — ‰.'),
           ('migration_change.png','Где выше миграционный прирост?',
            'Положительное значение означает чистый приток населения. Единица — ‰.'),
           ('fertility.png','Где выше суммарная рождаемость?',
            'Шкала означает среднее число детей на одну женщину; она не измеряет число рождений за год.')]
    for idx,(path,title,explain) in enumerate(names,start=4):
        chart_slide(title,'Тематическая карта • отдельная единица измерения и шкала для каждого показателя',idx,path,explain)

    sl=slide('География учитывается через связи соседей','Для каждого региона определяем четыре ближайшие территории и строим симметричный граф',8)
    card(sl,.83,2.20,5.65,3.98,'Что означает «сосед»','Соседство задаётся по расстоянию между внутренними опорными точками территорий.\nЕсли граф распадается, компоненты соединяются ближайшей допустимой связью.',CYAN,17)
    card(sl,6.75,2.20,5.65,3.98,'Почему это важно','K-Means не видит карту. Spatial Ward и MST используют граф — поэтому географическая структура может менять состав групп.',GOLD,18)
    note(sl,'Ограничение: «четыре ближайших» не равно «имеет общую границу»; это осознанное правило.')

    chart_slide('Похожи ли соседние территории?','Индекс Морана I — числовая проверка пространственной автокорреляции',9,
                'moran_global.png','Если I > 0, похожие значения чаще расположены рядом. Значимость оценивается по p.')

    sl=slide('Сравниваем три принципиально разных метода','Нельзя выбрать итоговую группировку по одному алгоритму без контроля',10)
    card(sl,.8,2.16,3.75,4.0,'K-Means','Объединяет регионы с близкими показателями.\nГеографическая связность НЕ обязательна.\nИспользуется как базовый метод.',CYAN,16)
    card(sl,4.76,2.16,3.75,4.0,'Spatial Ward','Объединяет похожие объекты, ограничивая процесс графом соседства.\nПолучаются географически связные группы.',GOLD,16)
    card(sl,8.72,2.16,3.75,4.0,'MST spatial','Создаёт дерево связей между территориями и удаляет наиболее неоднородные рёбра.\nКонтролирует территориальную связность.','779DF6',16)
    note(sl,'Каждый метод тестируется при числе кластеров k = 3, 4, 5 и 6.',y=6.7)

    sl=slide('Какое число групп лучше разделяет территории?','Silhouette: чем выше значение, тем отчётливее разделены кластеры',11)
    picture(sl,maps/'method_silhouette.png' if has_results else None,.52,2.02,8.71,4.55)
    if has_results:
        card(sl,9.35,2.23,3.45,4.17,'Почему этого мало',
             'Высокий силуэт не гарантирует связности на карте.\nПроверяем устойчивость и фрагментацию отдельно.',GOLD,16)
    else:
        card(sl,9.35,2.23,3.45,4.17,'Критерии выбора',
             'Silhouette — выше лучше.\nARI — выше устойчивость.\nФрагментация — меньше лучше.',GOLD,16)
    note(sl,('Линии — алгоритмы; точки — число групп. ПОКАЗАНЫ ВЫМЫШЛЕННЫЕ ДАННЫЕ.' if demo else 'Линии — алгоритмы; точки — число групп. График пересчитывается на реальных данных.'))

    sl=slide('Как различаются группы на карте?','Сравнение K-Means и Spatial Ward при выбранном числе кластеров',12)
    picture(sl,maps/'cluster_KMeans.png' if has_results else None,.40,2.14,6.19,4.47)
    picture(sl,maps/'cluster_Spatial_Ward.png' if has_results else None,6.74,2.14,6.19,4.47)
    note(sl,'Одинаковый цвет на двух картах НЕ означает одинаковый состав: номера групп условны.',y=6.65)

    sl=slide('Какой метод выбран и почему?','Слева — MST spatial; справа — вариант, выбранный по совокупности критериев',13)
    picture(sl,maps/'cluster_MST_spatial.png' if has_results else None,.40,2.14,6.19,4.47)
    picture(sl,maps/'clusters_final.png' if has_results else None,6.74,2.14,6.19,4.47)
    if has_results:
        note(sl,f"Выбран: {summary['best_method']} · k={summary['best_k']} · silhouette={summary['best_silhouette']:.2f} · ARI={summary['best_stability_ARI']:.2f}")
    else:
        note(sl,'Выбор определяется одновременно разделением, связностью, устойчивостью и размерами групп.')

    chart_slide('Чем конкретно различаются найденные группы?','Профиль кластеров: каждый показатель сравнивается со средним по рассматриваемым территориям',14,
                'cluster_profiles.png',
                'Красный — выше среднего, синий — ниже. +1 означает превышение на одно стандартное отклонение.')

    sl=slide('Что означают результаты — и чего они не доказывают','Пространственная кластеризация описывает сходство, но не причины изменений населения',15)
    card(sl,.82,2.15,5.73,4.05,'Можно утверждать','Сходство территорий по четырём показателям.\nСопоставимость полученных карт.\nЧувствительность к выбору метода и числа кластеров.',CYAN,17)
    card(sl,6.79,2.15,5.73,4.05,'Нельзя утверждать','«Хороший» или «плохой» регион только по цвету.\nПричинную связь географии и демографии.\nНеизменность групп в другие годы.',RED,17)
    note(sl,'Анализ относится к состоянию на 2021 год и к выбранному набору показателей.')

    sl=slide('Воспроизводимость и защита проекта','Код, отчёт и презентация; таблицы и карты на реальных данных создаются при запуске',16)
    card(sl,.83,2.21,5.68,4.05,'Что приложено','README.md — инструкция и ограничения\nsrc/ — полный Python-конвейер\nresults/ и maps/ — расчёты после запуска\ndocs/ — отчёт и доклад\npresentation/ — PPTX для защиты',CYAN,16)
    card(sl,6.73,2.21,5.68,4.05,'Источники','Статистика: github.com/tochno-st/regions_collection\n\nГраницы: github.com/imsha/russia_geojson_regions_2021\n\nСкрипт Start_Windows.bat выполняет расчёты на источниках 2021 года.',GOLD,15)
    note(sl,'Для защиты: 4 участника × ~2,5 минуты; после выступления — ответы и оппонирование.')

    r.save(out)
    return len(r.slides)

def style_document(doc):
    for section in doc.sections:
        section.top_margin=Cm(2);section.bottom_margin=Cm(2);section.left_margin=Cm(3);section.right_margin=Cm(1.5)
    s=doc.styles['Normal'];s.font.name='Times New Roman';s.font.size=DPt(14);s.font.color.rgb=DRGB(0,0,0)
    pf=s.paragraph_format;pf.line_spacing=1.5;pf.first_line_indent=Cm(1.25);pf.space_after=DPt(0)
    for name in ('Heading 1','Heading 2'):
        st=doc.styles[name];st.font.name='Times New Roman';st.font.size=DPt(14);st.font.bold=True;st.font.color.rgb=DRGB(0,0,0)
        st.paragraph_format.first_line_indent=Cm(0);st.paragraph_format.space_before=DPt(10);st.paragraph_format.space_after=DPt(6)
        st.paragraph_format.keep_with_next=True

def heading(doc,t):
    p=doc.add_paragraph(style='Heading 1');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.add_run(t)

def para(doc,t):return doc.add_paragraph(t)

def add_table(doc,headers,rows):
    tb=doc.add_table(rows=1,cols=len(headers));tb.style='Table Grid';tb.alignment=WD_TABLE_ALIGNMENT.CENTER
    for j,h in enumerate(headers):tb.rows[0].cells[j].text=str(h)
    for row in rows:
        cells=tb.add_row().cells
        for j,a in enumerate(row):cells[j].text=str(a)
    for row in tb.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.line_spacing=1
                for run in p.runs:run.font.name='Times New Roman';run.font.size=DPt(10)
    for cell in tb.rows[0].cells:
        for p in cell.paragraphs:
            for run in p.runs:run.bold=True
    return tb

def make_report(summary,out,results):
    active=bool(summary) and summary.get('status')=='completed_2021_data'
    doc=Document();style_document(doc)
    heading(doc,'Практические работы № 11–12 по дисциплине «Анализ данных и машинное обучение»')
    p=doc.add_paragraph('Команда № 3. Демографическая структура регионов Российской Федерации');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    heading(doc,'1. Цель и постановка исследования')
    para(doc,'Цель работы – выявить группы субъектов РФ, сходных по демографическим показателям за 2021 год, и проверить, как учёт географической близости влияет на итоговые кластеры. В отличие от регрессионной задачи, здесь отсутствует зависимая переменная: исследуется пространственная кластеризация четырёх признаков.')
    heading(doc,'2. Исходные данные')
    add_table(doc,['Код','Наименование','Условная переменная'],[(c,nm,short) for short,(c,nm) in {
        'urban_share':('01030000','Доля городского населения, %'),
        'natural_change':('01140000','Коэффициент естественного прироста, ‰'),
        'migration_change':('01200000','Коэффициент миграционного прироста, ‰'),
        'fertility':('01150000','Суммарный коэффициент рождаемости')}.items()])
    para(doc,'Источник статистики – открытый репозиторий «Если быть точным» (Росстат), раздел «Население» за 2021 год. Источник геометрии – открытый набор GeoJSON субъектов РФ. Общероссийские итоги и федеральные округа исключаются до анализа. Различие территориальных охватов фиксируется в журнале объединения.')
    heading(doc,'3. Подготовка геопространственной базы')
    para(doc,'Проверяется выбор года, коды показателей, названия субъектов, отсутствие дублей, типы числовых данных, пропуски, система координат EPSG:4326 и корректность полигонов. Разные написания наименований унифицируются по явным правилам. Неоднозначные совпадения не соединяются автоматически. Субъекты с неполным набором четырёх значений исключаются из сравнения; перечень сохраняется. На картах неполные и несопоставленные регионы сохраняют геометрию и обозначаются серым со штриховкой, а не искусственным цветом кластера. Точный перечень: results/excluded_regions_map.csv.')
    heading(doc,'4. Разведочный и пространственный анализ')
    para(doc,'Для каждого показателя рассчитываются среднее, медиана, стандартное отклонение, минимум, максимум, асимметрия и карта значений. Пространственная схема W – симметризированный граф четырёх ближайших полигонов по расстоянию между их внутренними опорными точками. Для разделённых компонент используются минимальные дополнительные рёбра, которые записываются в журнал.')
    para(doc,'Глобальный индекс Морана I оценивает сходство показателей у соседних регионов. Значимость проверяется 399 перестановками. Для локального индекса Морана вычисляются ориентировочные перестановочные p-value и поправка Бенджамини–Хохберга на множественные проверки.')
    heading(doc,'5. Алгоритмы и параметры')
    para(doc,'Четыре признака стандартизируются: из каждого значения вычитается среднее и выполняется деление на стандартное отклонение. Сравниваются K-Means без географических ограничений, пространственно-ограниченная агломеративная кластеризация Ward и кластеризация по минимальному остовному дереву графа соседства (MST spatial). Для каждого метода исследуется k = 3, 4, 5 и 6.')
    para(doc,'Оценка качества включает коэффициент силуэта, индекс Дэвиса–Болдина, число компонент связности, минимальный размер группы и ARI при небольших случайных возмущениях матрицы признаков. Для дополнительной проверки сравниваются StandardScaler и RobustScaler. Итог выбирается по заранее заданному составному показателю и предметной интерпретируемости.')
    heading(doc,'6. Результаты вычислений')
    if active:
        para(doc,f"В исходную полную аналитическую выборку вошло {summary['n_regions']} субъектов с четырьмя наблюдаемыми показателями. Пропуски привели к исключению {summary['excluded_missing']} субъектов. По выбранному правилу сравнения предпочтительнее метод {summary['best_method']} с k = {summary['best_k']}; silhouette = {summary['best_silhouette']:.3f}, устойчивость ARI = {summary['best_stability_ARI']:.3f}.")
        M=pd.read_csv(results/'global_moran.csv')
        add_table(doc,['Код','Moran I','p (перестановки)','Локальные q<0,05'],[(str(r.indicator_code),f'{r.Moran_I:.3f}',f'{r.permutation_p:.4f}',int(r.local_FDR05_n)) for _,r in M.iterrows()])
        R=pd.read_csv(results/'method_comparison.csv').sort_values('balanced_score',ascending=False)
        add_table(doc,['Метод','k','Silhouette','ARI','Компоненты'],[(r.method,int(r.k),f'{r.silhouette:.3f}',f'{r.stability_ARI:.3f}',int(r.connected_components)) for _,r in R.head(8).iterrows()])
        para(doc,'Карты для каждого показателя, трёх алгоритмов и итогового разбиения представлены в каталоге maps/. Полная таблица присвоения регионов кластерам – results/regional_clusters.csv. Приводимые ниже интерпретации описывают совпадения и различия, но не причинные связи.')
    else:
        para(doc,'На момент создания отчёта исходные внешние архивы статистики и географических границ не удалось скачать в данной среде. Числовые выводы о субъектах России не рассчитывались и не подменялись синтетическими результатами. Исполняемый конвейер и проверочный отдельный тестовый набор готовы; после запуска Start_Windows.bat на устройстве с доступом к источникам раздел, таблицы, карты и презентация будут сформированы автоматически.')
    heading(doc,'7. Достоверность, ограничения и выводы')
    para(doc,'Сравнение проведено только для 2021 года; группы могут измениться при других годах или наборе показателей. Количество соседей, методы стандартизации, географическое покрытие и разные размеры территорий способны повлиять на результат. Некоторые субъекты являются географическими анклавами или имеют удалённые части. Пространственное совпадение не доказывает влияния географии на демографию.')
    if active:
        para(doc,'Цель исследования выполнена: сформировано территориально привязанное кластерное разбиение, проведено сравнение трёх семейств методов, сохранены метрики и карты для независимой проверки. Интерпретация каждой группы должна основываться на профиле её четырёх показателей и списке вошедших субъектов.')
    else:
        para(doc,'На текущем этапе выполнены постановка задачи, реализация и технический тест конвейера. Эмпирическая часть по субъектам РФ требует загрузки открытых источников и повторного запуска. Эта граница воспроизводимости зафиксирована, чтобы не выдавать демонстрационный расчёт за результаты исследования.')
    heading(doc,'8. Воспроизведение и состав проекта')
    para(doc,'Установка и запуск: Start_Windows.bat (Python 3.10+, интернет, 7-Zip для RAR). После запуска появляются results/ с метриками, maps/ с картами, presentation/ с PowerPoint и docs/ с отчётом. Для проверки алгоритмов без внешних данных предусмотрен Start_DEMO_Windows.bat, результаты которого маркируются как синтетические и сохраняются отдельно.')
    heading(doc,'Источники')
    para(doc,'1. «Если быть точным». Социально-экономические показатели регионов России (на основе Росстата), 2000–2021. https://github.com/tochno-st/regions_collection')
    para(doc,'2. imsha. Russia GeoJSON regions 2021. https://github.com/imsha/russia_geojson_regions_2021')
    path=D/out;doc.save(path)
    return path

def make_speakers():
    d=Document();style_document(d)
    heading(d,'Памятка для защиты. Команда № 3')
    blocks=[
      ('Участник 1 · 0:00–2:15','Мы исследовали демографическую структуру регионов России за 2021 год. Наша цель – не предсказать отдельное число, а найти группы регионов, похожих друг на друга. Для этого выбрали четыре характеристики: долю городского населения, естественный прирост, миграционный прирост и суммарную рождаемость. Все показатели взяты из указанного в задании источника, а границы – из отдельного GeoJSON.'),
      ('Участник 2 · 2:15–4:45','Сначала мы привели статистику и географию к общему набору регионов, проверили пропуски и построили карты. Одна из главных идей геопространственного анализа – учитывать соседей. Мы построили граф из четырёх ближайших регионов и рассчитали индекс Морана. Он показывает, склонны ли похожие значения находиться рядом.'),
      ('Участник 3 · 4:45–7:30','Мы сравниваем три подхода. K-Means группирует по значениям без географии. Spatial Ward ограничивает объединение графом соседства. MST spatial строит дерево ближайших географических связей и разделяет его по различию характеристик. Мы проверяем несколько чисел кластеров и оцениваем силуэт, устойчивость и территориальную связность.'),
      ('Участник 4 · 7:30–10:00','Лучшим мы считаем не обязательно самый красивый рисунок на карте, а результат, который одновременно достаточно однороден по показателям, устойчив при изменении данных и имеет понятную географическую структуру. Главное ограничение исследования – один год и выбранные четыре признака. Кластеры описывают сходство, но не доказывают причины демографических различий.')]
    for h,t in blocks:heading(d,h);para(d,t)
    heading(d,'Вопросы оппонентов и короткие ответы')
    qas=[('Почему не только K-Means?','Он не учитывает, что регионы занимают конкретные места на карте; сравнение с пространственными методами показывает цену этого ограничения.'),
         ('Зачем стандартизировать?','У показателей разные единицы измерения и разброс. Без стандартизации один показатель может подавить остальные.'),
         ('Что означает индекс Морана?','Положительное значение обычно означает, что у соседей похожие значения; p-value проверяется перестановками.'),
         ('Почему четыре ближайших соседа?','Это воспроизводимая схема без изолированных регионов; результат чувствителен к выбору k, это ограничение.'),
         ('Почему один год недостаточен?','По одному срезу нельзя определить динамику и делать причинные выводы. Для этого нужны данные за несколько лет.'),
         ('Где все результаты?','Таблицы находятся в results/, карты – в maps/, а порядок воспроизведения – в README.md.')]
    for q,a in qas:para(d,'Вопрос: '+q);para(d,'Ответ: '+a)
    d.save(D/'Speech_4_People.docx')

def main(demo=False):
    resultdir=ROOT/('results_demo' if demo else 'results')
    maps=ROOT/('maps_demo' if demo else 'maps')
    meta=resultdir/'summary.json'
    data=json.loads(meta.read_text(encoding='utf-8')) if meta.exists() else None
    if data and not demo and data.get('status')!='completed_2021_data':data=None
    pres_name='Team3_Demography_DEMO.pptx' if demo else 'Team3_Demography_2021.pptx'
    report_name='Report_Team3_DEMO.docx' if demo else 'Report_Team3.docx'
    slides=make_ppt(data,O/pres_name,maps,demo)
    make_report(data,report_name,resultdir)
    if not demo:make_speakers()
    print('PRESENTATION:',O/pres_name,':',slides,'slides')
    print('REPORT:',D/report_name)
    print('DATA STATUS:',data.get('status') if data else 'external data unavailable; no empirical estimates')
    return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--demo',action='store_true');sys.exit(main(p.parse_args().demo))
