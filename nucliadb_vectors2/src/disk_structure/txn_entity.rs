use std::{
    fs::File,
    io::{BufReader, BufWriter},
    path::Path,
};

use super::{errors::DiskStructResult, DiskReadable, DiskWritable, DELETE_LOG, SEGMENT};
use crate::{delete_log::DeleteLog, segment::Segment};

pub(crate) struct TxnEntity<'a> {
    pub base_path: &'a Path,
    pub txn_id: usize,
}

impl<'a> TxnEntity<'a> {
    pub fn create(txn_id: usize) -> DiskStructResult<()> {
        Ok(())
    }
}

impl<'a> DiskReadable<Segment> for TxnEntity<'a> {
    fn read(&self) -> DiskStructResult<Segment> {
        let txn_path = format!("txn_{}", self.txn_id);
        Ok(Segment::new(
            self.base_path.join(SEGMENT).join(txn_path).as_path(),
        ))
    }
}

impl<'a> DiskReadable<DeleteLog> for TxnEntity<'a> {
    fn read(&self) -> DiskStructResult<DeleteLog> {
        let txn_path = format!("txn_{}", self.txn_id);
        let reader = BufReader::new(File::open(self.base_path.join(DELETE_LOG).join(txn_path))?);
        Ok(bincode::deserialize_from(reader)?)
    }
}

impl<'a> DiskWritable<DeleteLog> for TxnEntity<'a> {
    fn write(&self, data: DeleteLog) -> DiskStructResult<()> {
        let txn_path = format!("txn_{}", self.txn_id);
        let writer = BufWriter::new(File::open(self.base_path.join(DELETE_LOG).join(txn_path))?);
        Ok(bincode::serialize_into(writer, &data)?)
    }
}
