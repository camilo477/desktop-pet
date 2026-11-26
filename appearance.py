"""Local coat palettes and independent eye and nose choices."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Appearance:
    coat: str = 'original'
    eyes: str = 'auto'
    nose: str = 'auto'


@dataclass(frozen=True)
class Coat:
    name: str
    # Empty swatches use the original artwork. Light and shade follow its volumes.
    base: str = ''
    light: str = ''
    shade: str = ''
    leg: str = ''
    inner: str = ''
    whisker: str = ''
    lid: str = ''
    nose: str = ''
    eyes: str = 'gold'
    pattern: str = ''
    ink: str = ''
    accent: str = ''
    tail: str = ''
    ears: tuple = ()
    toes: tuple = ()
    feet: tuple = ()


COATS = {
    'original': Coat('Miga original'),
    'black': Coat('Negro sólido', '#24262c', '#292c33', '#181b22', '#252831',
                  '#51454d', '#92939a', '#848893', '#191920', 'green'),
    'ginger': Coat('Naranja atigrado', '#d8985c', '#e9af72', '#ba7b49', '#d99b60',
                   '#c58a79', '#7f6352', '#76513b', '#b7766c', 'green',
                   'tabby', '#ad6940', '#f0c893'),
    'blue': Coat('Gris sólido', '#8494a2', '#94a3af', '#687887', '#8a99a5',
                 '#a48e97', '#4d5c69', '#43535e', '#55555e', 'copper'),
    'silver': Coat('Gris atigrado', '#9b9e9b', '#b4b5ac', '#7e847f', '#a6a9a1',
                   '#bc9c99', '#5b625e', '#49534d', '#9e7972', 'green',
                   'tabby', '#686e68', '#d6d4c8'),
    'white': Coat('Blanco', '#e1ddd4', '#efebe2', '#c6c0b7', '#e4dfd7',
                  '#d8aca9', '#8a827b', '#857971', '#c98e8b', 'hazel'),
    'bicolor': Coat('Bicolor', '#e0dcd2', '#eeebe2', '#c5bfb5', '#e3dfd6',
                    '#c4a4a0', '#88817d', '#858383', '#b67f7e', 'green',
                    'piebald', '#44454a', tail='#424348', ears=('#414247','#555459'),
                    toes=('#e6e0d5','#6a6868'), feet=('#cdc8be','#534f50')),
    'tuxedo': Coat('Tuxedo', '#303237', '#3a3c40', '#23252a', '#34363b',
                   '#80676e', '#a2a2a0', '#939193', '#27262a', 'gold',
                   'bib', '#dfdcd2', toes=('#e5e1d6','#e5e1d6'), feet=('#c5c1b7','#c5c1b7')),
    'siamese': Coat('Siamés', '#cfbba3', '#e1d0b8', '#b39e88', '#bda88f',
                    '#997c79', '#9c9290', '#c9b9ac', '#46393a', 'blue',
                    'point', '#665349', '#998270', tail='#68574e', ears=('#66544c','#5d4c46'),
                    toes=('#65534c','#65534c'), feet=('#897467','#897467')),
    'calico': Coat('Calicó', '#e3dbcc', '#f0e8d9', '#c8beae', '#e2dacb',
                   '#d0a7a0', '#92867d', '#837773', '#bb8482', 'hazel',
                   'patches', '#444248', '#d49454', tail='#d49a64', ears=('#49454a','#bd8456'),
                   toes=('#ece4d5','#e8dece'), feet=('#cba16d','#cec5b7')),
    'tortie': Coat('Carey', '#453e3e', '#534948', '#352f31', '#494040',
                   '#9b7873', '#b7a697', '#ada098', '#6c5654', 'amber',
                   'brindle', '#b7835c', '#8b634d', tail='#494041',
                   ears=('#544443','#a57859'), toes=('#84614e','#544443')),
}

EYES = {
    'auto': ('Automático', ''), 'gold': ('Dorado', '#dcc36e'), 'amber': ('Ámbar', '#e2ad5d'),
    'green': ('Verde', '#a9c188'), 'blue': ('Azul', '#97cbe0'), 'hazel': ('Avellana', '#b8b078'),
    'copper': ('Cobre', '#cc8a5c'), 'gray': ('Gris', '#adbec5'),
    'odd': ('Heterocromía', ''),
}
NOSES = {
    'auto': ('Automático', ''), 'black': ('Negro', '#252429'), 'gray': ('Gris oscuro', '#595962'),
    'pink': ('Rosado', '#ca9090'), 'brown': ('Marrón cálido', '#946852'),
}
