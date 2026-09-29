import json, tempfile, unittest, zipfile
from pathlib import Path
from pbidocgen.live_connection import describe, from_pbix, from_pbir, redact


class LiveConnectionTests(unittest.TestCase):
    def test_redacts_credentials_and_classifies_aas(self):
        live = describe('Data Source=asazure://uks.asazure.windows.net/srv;Initial Catalog=Sales;Password=x;User ID=u')
        self.assertEqual(live['kind'], 'Azure Analysis Services')
        self.assertEqual(live['database'], 'Sales')
        self.assertNotIn('Password', live['connectionString'])
        self.assertNotIn('User ID', redact('User ID=u;Data Source=a'))

    def test_pbix_connections_part(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'a.pbix'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('Connections', json.dumps({'Connections': [{'ConnectionString':
                    'Data Source=localhost;Initial Catalog=Cube'}]}))
            live = from_pbix(path)
        self.assertEqual((live['kind'], live['database']), ('SQL Server Analysis Services', 'Cube'))

    def test_pbir_by_connection(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'definition.pbir').write_text(json.dumps({'datasetReference': {'byConnection': {
                'connectionString': 'Data Source=asazure://a/b;Initial Catalog=C'}}}))
            self.assertEqual(from_pbir(Path(d))['server'], 'asazure://a/b')
            self.assertIsNone(from_pbir(Path(d) / 'missing'))


if __name__ == '__main__':
    unittest.main()
