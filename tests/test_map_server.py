import functools
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('serve_maps',ROOT/'scripts/serve_maps.py')
maps=importlib.util.module_from_spec(spec)
spec.loader.exec_module(maps)


class MapServerTests(unittest.TestCase):
    def test_get_and_head_only_serve_allowed_map_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'index.html').write_text('<h1>Map</h1>',encoding='utf-8')
            (Path(tmp)/'private.txt').write_text('Must not be served',encoding='utf-8')
            server=maps.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(maps.Handler,directory=tmp))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                base=f'http://127.0.0.1:{server.server_port}'
                for method in ['GET','HEAD']:
                    with urllib.request.urlopen(urllib.request.Request(base+'/index.html',method=method)) as response:
                        self.assertEqual(response.status,200)
                        self.assertEqual(response.headers['Cache-Control'],'no-store')
                    with self.assertRaises(urllib.error.HTTPError) as failure:
                        urllib.request.urlopen(urllib.request.Request(base+'/private.txt',method=method))
                    self.assertEqual(failure.exception.code,403)
                    failure.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
