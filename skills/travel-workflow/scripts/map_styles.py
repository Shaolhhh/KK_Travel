import hashlib
from pathlib import Path
from PIL import ImageFont


def font(size,bold=False):
    paths=[Path('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path),size)
    raise RuntimeError('静态图需要中文字体：Microsoft YaHei或Noto Sans CJK')


def stable_ids(element,prefix='0'):
    element._id=hashlib.sha256(prefix.encode()).hexdigest()[:20]
    children=[]
    for i,(key,child) in enumerate(element._children.items()):
        old_name=child.get_name()
        stable_ids(child,f'{prefix}-{i}')
        children.append((child.get_name() if key==old_name else key,child))
    element._children=dict(children)
    for name in ('header','html','script'):
        value=getattr(element,name,None)
        if hasattr(value,'_children'):
            stable_ids(value,f'{prefix}-{name}')
