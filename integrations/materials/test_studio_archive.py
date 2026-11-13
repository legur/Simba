import hashlib
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import studio_archive as archive


class Request:
    def __init__(self, data): self.data = data
    def execute(self, num_retries=0): return self.data


class FakeDrive:
    def __init__(self):
        self.nodes = {archive.ROOT_FOLDER: {'id': archive.ROOT_FOLDER, 'mimeType':'application/vnd.google-apps.folder'}}
        self.payloads = {}
        self.created = 0
        self.broad = False
    def files(self): return self
    def get(self, fileId, fields):
        node = dict(self.nodes[fileId])
        node.update({'permissions':[{'type':'anyone' if self.broad else 'user'}], 'capabilities':{'canAddChildren':True}})
        return Request(node)
    def list(self, q, fields, pageSize):
        parent, name = re.match(r"'([^']+)' in parents and name = '([^']+)'", q).groups()
        return Request({'files':[dict(v) for v in self.nodes.values() if v.get('parents') == [parent] and v.get('name') == name]})
    def create(self, body, fields, media_body=None):
        self.created += 1
        node = {'id':f'id-{self.created}', **body}
        if media_body is not None:
            data=media_body.data
            node.update({'size':str(len(data)), 'md5Checksum':hashlib.md5(data).hexdigest()})
            self.payloads[node['id']] = data
        self.nodes[node['id']] = node
        return Request(dict(node))
    def get_media(self, fileId): return Request(self.payloads[fileId])
    def copy(self, fileId, body, fields):
        return self.create(body, fields, Media(self.payloads[fileId], None, False))


class Media:
    def __init__(self, data, mimetype, resumable): self.data=data


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        http=types.ModuleType('googleapiclient.http'); http.MediaInMemoryUpload=Media
        google=types.ModuleType('googleapiclient')
        p=patch.dict(sys.modules, {'googleapiclient':google, 'googleapiclient.http':http})
        p.start(); self.addCleanup(p.stop)
        self.drive=FakeDrive()

    def test_creates_individual_files_and_reuses_verified_copies(self):
        first=archive.save_files(self.drive,'project-1','storyboard',{'scene.jpg':b'image', 'manifest.json':b'{}'})
        self.assertEqual(first['status'],'INDIVIDUAL_FILES_VERIFIED')
        count=self.drive.created
        second=archive.save_files(self.drive,'project-1','storyboard',{'scene.jpg':b'image', 'manifest.json':b'{}'})
        self.assertEqual(self.drive.created,count)
        self.assertTrue(all(f['reused'] for f in second['files']))

    def test_refuses_public_folder_and_name_collision(self):
        self.drive.broad=True
        with self.assertRaises(archive.ArchiveError): archive.save_files(self.drive,'p','storyboard',{'x.jpg':b'x'})
        self.assertEqual(self.drive.created,0)
        self.drive.broad=False
        archive.save_files(self.drive,'p','storyboard',{'x.jpg':b'x'})
        with self.assertRaises(archive.ArchiveError): archive.save_files(self.drive,'p','storyboard',{'x.jpg':b'y'})

    def test_rejects_remote_byte_corruption(self):
        result=archive.save_files(self.drive,'p','storyboard',{'x.jpg':b'x'})
        self.drive.payloads[result['files'][0]['drive_file_id']]=b'z'
        with self.assertRaises(archive.ArchiveError): archive.save_files(self.drive,'p','storyboard',{'x.jpg':b'x'})

    def test_rejects_path_or_empty_data(self):
        with self.assertRaises(archive.ArchiveError): archive.save_files(self.drive,'../p','storyboard',{'x':b'x'})
        with self.assertRaises(archive.ArchiveError): archive.save_files(self.drive,'p','storyboard',{'../x':b'x'})
        with self.assertRaises(archive.ArchiveError): archive.save_files(self.drive,'p','storyboard',{'x':b''})

    def test_copies_existing_large_result_once_and_rejects_collision(self):
        source_id='source-file-12345'
        data=b'rendered-result'
        self.drive.nodes[source_id]={'id':source_id, 'name':'render.mp4', 'mimeType':'video/mp4',
                                     'size':str(len(data)), 'md5Checksum':hashlib.md5(data).hexdigest()}
        self.drive.payloads[source_id]=data
        first=archive.copy_files(self.drive,'p','results',{'render.mp4':source_id})
        count=self.drive.created
        second=archive.copy_files(self.drive,'p','results',{'render.mp4':source_id})
        self.assertEqual(first['status'],'INDIVIDUAL_COPIES_VERIFIED')
        self.assertTrue(second['files'][0]['reused'])
        self.assertEqual(self.drive.created,count)
        self.drive.nodes[source_id]['md5Checksum']='a'*32
        with self.assertRaises(archive.ArchiveError):
            archive.copy_files(self.drive,'p','results',{'render.mp4':source_id})
