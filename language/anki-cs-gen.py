import sqlite3
from gtts  import gTTS
import genanki

conn = sqlite3.connect('collection.anki2')
c = conn.cursor()

deck = genanki.Deck(2059400110, 'Tschechisch Deutsch (Talki)')

model = genanki.Model(
    1607392319,
    'Simple Model',
    fields=[
        {'name': 'Tschechisch'},
        {'name': 'Deutsch'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '{{Tschechisch}}',
            'afmt': '{{FrontSide}}<hr id="answer">{{Deutsch}}',
        },
    ])

package = genanki.Package(deck)

mediafiles = []

for row in c.execute('''SELECT guid, flds from notes'''):
    guid = hex(hash(row[0]))
    deu, cze = row[1].split('\x1f')

    tts = gTTS(cze, 'cs')
    with open('{}.mp3'.format(guid), 'wb') as f:
        tts.write_to_fp(f)

    mediafiles.append('{}.mp3'.format(guid))
    my_note = genanki.Note(
        model=model,
        fields=['{}, [sound:{}.mp3]'.format(cze, guid),
                deu])
    
    deck.add_note(my_note)
    print('{};{};{}'.format(guid,cze,deu))

package.media_files = mediafiles
package.write_to_file('output.apkg')
