"""Serve only generated map assets on IPv4 loopback; never serve the repository."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

class Handler(SimpleHTTPRequestHandler):
    def list_directory(self,path):
        self.send_error(403,'Directory listing disabled')
        return None

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()

    def send_head(self):
        candidate=Path(self.translate_path(self.path)).resolve()
        if not candidate.is_relative_to(Path(self.directory).resolve()) or (candidate.is_file() and candidate.suffix not in ('.html','.geojson','.png','.js','.css')):
            self.send_error(403)
            return
        return super().send_head()

def serve(directory,port=8765):
    directory=Path(directory).resolve()
    if directory.name not in ('site','maps') or not directory.is_dir():
        raise ValueError('只能预览已生成的 site 或 maps 目录，不可暴露项目根目录')
    server=ThreadingHTTPServer(('127.0.0.1',port),partial(Handler,directory=str(directory)))
    print(f'Local map preview: http://127.0.0.1:{port}/',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    serve(args.directory,args.port)
