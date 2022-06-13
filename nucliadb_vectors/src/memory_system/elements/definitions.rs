// Copyright (C) 2021 Bosutech XXI S.L.
//
// nucliadb is offered under the AGPL v3.0 and as commercial software.
// For commercial licensing, contact us at info@nuclia.com.
//
// AGPL:
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <http://www.gnu.org/licenses/>.
//

use std::collections::HashMap;

use serde::{Deserialize, Serialize};
use std::iter::Iterator;

pub const VECTORS_DIR: &str = "vectors";

pub trait Distance {
    fn cosine(i: &Self, j: &Self) -> f32;
}

pub mod hnsw_params {
    pub fn level_factor() -> f64 {
        1.0 / (m() as f64).ln()
    }
    pub const fn m_max() -> usize {
        30
    }
    pub const fn m() -> usize {
        30
    }
    pub const fn ef_construction() -> usize {
        100
    }
    pub const fn k_neighbours() -> usize {
        10
    }
}

#[derive(Copy, Clone, Serialize, Deserialize)]
pub enum LogField {
    VersionNumber = 0,
    EntryPoint,
    NoLayers,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct EntryPoint {
    pub node: Node,
    pub layer: u64,
}

impl From<(Node, usize)> for EntryPoint {
    fn from((node, layer): (Node, usize)) -> EntryPoint {
        EntryPoint {
            node,
            layer: layer as u64,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct FileSegment {
    pub start: u64,
    pub end: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, PartialOrd, Eq, Ord, Hash, Serialize, Deserialize)]
pub struct Node {
    pub vector: FileSegment,
}

#[derive(Clone, Copy, Debug, PartialEq, PartialOrd, Serialize, Deserialize)]
pub struct Edge {
    pub from: Node,
    pub to: Node,
    pub dist: f32,
}

#[derive(Clone, PartialEq, PartialOrd, Debug, Serialize, Deserialize)]
pub struct Vector {
    pub raw: Vec<f32>,
}

impl From<Vec<f32>> for Vector {
    fn from(raw: Vec<f32>) -> Self {
        Vector { raw }
    }
}

impl From<Vector> for Vec<f32> {
    fn from(v: Vector) -> Self {
        v.raw
    }
}


pub struct Connexions(HashMap<Node, Edge>);
impl std::iter::IntoIterator for Connexions {
    type IntoIter = std::collections::hash_map::IntoValues<Node, Edge>;
    type Item = Edge;
    fn into_iter(self) -> Self::IntoIter {
        self.0.into_values()
    }
}

#[derive(Clone, Serialize, Deserialize)]
pub struct GraphLayer {
    pub cnx: HashMap<Node, HashMap<Node, Edge>>,
}

impl Default for GraphLayer {
    fn default() -> Self {
        GraphLayer::new()
    }
}

impl std::ops::Index<Node> for GraphLayer {
    type Output = HashMap<Node, Edge>;
    fn index(&self, from: Node) -> &Self::Output {
        &self.cnx[&from]
    }
}
impl std::ops::Index<(Node, Node)> for GraphLayer {
    type Output = Edge;
    fn index(&self, (from, to): (Node, Node)) -> &Self::Output {
        &self.cnx[&from][&to]
    }
}

impl GraphLayer {
    pub fn new() -> GraphLayer {
        GraphLayer {
            cnx: HashMap::new(),
        }
    }
    pub fn has_node(&self, node: Node) -> bool {
        self.cnx.contains_key(&node)
    }
    pub fn add_node(&mut self, node: Node) {
        self.cnx.insert(node, HashMap::new());
    }
    pub fn add_edge(&mut self, node: Node, edge: Edge) {
        let edges = self.cnx.entry(node).or_insert_with(HashMap::new);
        edges.insert(edge.to, edge);
    }
    pub fn remove_node(&mut self, node: Node) {
        self.cnx.remove(&node);
    }
    pub fn full_disconnexion(&mut self, from: Node) -> Connexions {
        Connexions(std::mem::take(&mut self.cnx[&from]))
    }
    pub fn get_edges(&self, from: Node) -> impl Iterator<Item = &Edge> {
        self.cnx[&from].values()
    }
    pub fn no_edges(&self, node: Node) -> usize {
        self.cnx.get(&node).map(|v| v.len()).unwrap_or_default()
    }
    pub fn no_nodes(&self) -> usize {
        self.cnx.len()
    }
    pub fn remove_edge(&mut self, from: Node, to: Node) {
        let edges = self.cnx.get_mut(&from).unwrap();
        edges.remove(&to);
    }
    pub fn some_node(&self) -> Option<Node> {
        self.cnx.keys().next().cloned()
    }
    pub fn is_empty(&self) -> bool {
        self.cnx.len() == 0
    }
}
#[derive(Clone, Serialize, Deserialize)]
pub struct GraphLog {
    pub version_number: u128,
    pub max_layer: u64,
    pub entry_point: Option<EntryPoint>,
}
