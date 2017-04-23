# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Classes to read, validate and work with the input data files.
"""
import logging
from collections import OrderedDict
from pathlib import Path
from astropy.utils import lazyproperty
from astropy.table import Table
from .info import gammacat_info, gammacat_tag
from .input import InputData
from .sed import SEDList
from .utils import write_json, load_json

__all__ = [
    'OutputDataConfig',
    'OutputData',
    'OutputDataMaker',
]

log = logging.getLogger(__name__)


def log_list_difference(actual, expected):
    missing = sorted(set(expected) - set(actual))
    if missing:
        log.error('Missing: {}'.format(missing))

    extra = sorted(set(actual) - set(expected))
    if extra:
        log.error('Extra: {}'.format(extra))


class OutputDataConfig:
    """
    Configuration options (mainly directory and filenames).
    """
    path = gammacat_info.base_dir / 'docs/data'

    gammacat_yaml = path / 'gammacat.yaml'  # TODO: generate from here!
    gammacat_ecsv = path / 'gammacat.ecsv'
    gammacat_fits = path / 'gammacat.fits.gz'

    # Index files
    index_datasets_json = path / 'gammacat-datasets.json'
    index_sources_json = path / 'gammacat-sources.json'

    @staticmethod
    def make_filename(meta, datatype, relative=False):
        tag = gammacat_tag.source_dataset_filename(meta)

        if relative:
            base_path = Path('')
        else:
            base_path = OutputDataConfig.path

        source_path = base_path / 'sources' / gammacat_tag.source_str(meta)

        if datatype == 'sed':
            path = source_path / '{}_sed.ecsv'.format(tag)
        elif datatype == 'lc':
            path = source_path / '{}_lc.ecsv'.format(tag)
        else:
            raise ValueError('Invalid datatype: {}'.format(datatype))

        return path


class OutputData:
    """Access data from the output folder.

    Expose it as Python objects that can be validated and used.
    """

    def __init__(self, index_dataset=None, index_sources=None,
                 gammacat=None):
        self.path = OutputDataConfig.path
        self.index_dataset = index_dataset
        self.index_sources = index_sources
        self.gammacat = gammacat

    @classmethod
    def read(cls):
        """Read all data from disk.
        """
        path = OutputDataConfig.gammacat_fits
        gammacat = Table.read(str(path), format='fits')

        index_dataset = load_json(OutputDataConfig.index_datasets_json)
        index_sources = load_json(OutputDataConfig.index_sources_json)

        return cls(
            index_dataset=index_dataset,
            index_sources=index_sources,
            gammacat=gammacat,
        )

    def __str__(self):
        ss = 'Output data summary:\n'
        ss += 'Path: {}\n'.format(self.path)
        ss += 'Number of sources: {}\n'.format(len(self.gammacat))
        ss += 'Number of datasets: {}\n'.format(len(self.index_dataset['data']))
        ss += 'Number of files: {}\n'.format(len(self.index_dataset['files']))
        return ss

    def validate(self):
        log.info('Validating output data ...')

        self.validate_list_of_files()
        # TODO:
        # self.gammacat.validate()
        # self.datasets.validate()
        # self.seds.validate()
        # # self.lightcurves.validate()
        # self.gammacat_dataset_config.validate(self)

    def validate_list_of_files(self):
        actual = self.list_of_files()
        expected = self.index_dataset['files']
        log_list_difference(actual, expected)

        expected_files_sed = [
            str(OutputDataConfig.make_filename(sed.table.meta, 'sed', relative=True))
            for sed in SEDList.read().data
        ]

        expected_files_extra = [
            'README.md',
            'gammacat-datasets.json',
            'gammacat-sources.json',
            'gammacat.fits.gz',
            'gammacat.ecsv',
            'gammacat.yaml',
        ]

        expected_files = expected_files_extra + expected_files_sed
        log_list_difference(actual, expected_files)

    def list_of_files(self, pattern='*'):
        return list([
            str(_.relative_to(self.path))
            for _ in self.path.rglob(pattern)
            if _.is_file()
        ])


class OutputDataMaker:
    """
    Generate output data from input data.

    TODO: some of the columns are lists and can't be written to FITS.
    Remove those or replace with comma-separated strings.
    """

    def __init__(self):
        pass

    @lazyproperty
    def input_data(self):
        log.info('Reading input data ...')
        return InputData.read()

    def make_all(self):
        self.make_sed_files()
        self.make_index_files()

    def make_index_files(self):
        self.make_index_files_datasets()
        self.make_index_files_sources()

    def make_index_files_datasets(self):
        data = OrderedDict()
        data['info'] = gammacat_info.info_dict
        # TODO: the following line should be changed to OUTPUT
        data['data'] = self.input_data.datasets.to_dict()['data']
        data['files'] = OutputData().list_of_files()
        path = OutputDataConfig.index_datasets_json
        write_json(data, path)

    def make_index_files_sources(self):
        data = OrderedDict()
        data['info'] = gammacat_info.info_dict
        data['data'] = self.input_data.sources.to_dict()['data']
        path = OutputDataConfig.index_sources_json
        write_json(data, path)

    def make_sed_files(self):
        for sed in self.input_data.seds.data:
            log.debug('Processing SED: {}'.format(sed.path))
            sed.process()
            path = OutputDataConfig.make_filename(meta=sed.table.meta, datatype='sed')
            path.parent.mkdir(parents=True, exist_ok=True)
            log.info('Writing {}'.format(path))
            sed.table.write(str(path), format='ascii.ecsv')
