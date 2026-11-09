mod start_cuts;
mod start_cuts_opti;
use std::collections::{HashMap, HashSet};
use std::io::Read;

pub struct TreeNode { pub label: String, pub children: Vec<TreeNode> }
pub type ProcessForest = Vec<TreeNode>;

fn render(node: &TreeNode) -> String {
    if node.children.is_empty() { node.label.clone() }
    else { format!("{}({})", node.label, node.children.iter().map(render).collect::<Vec<_>>().join(",")) }
}

fn main() {
    // Input: one graph per block separated by "---"; lines "A\tx", "S\tx", "E\tx", "D\tx\ty".
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).unwrap();
    for block in input.split("---\n") {
        if block.trim().is_empty() { continue; }
        let (mut acts, mut starts, mut ends) = (HashSet::new(), HashSet::new(), HashSet::new());
        let mut dfg: HashMap<(String, String), usize> = HashMap::new();
        for line in block.lines() {
            let parts: Vec<&str> = line.split('\t').collect();
            match parts[0] {
                "A" => { acts.insert(parts[1].to_string()); }
                "S" => { starts.insert(parts[1].to_string()); }
                "E" => { ends.insert(parts[1].to_string()); }
                "D" => { dfg.insert((parts[1].to_string(), parts[2].to_string()), 1); }
                _ => {}
            }
        }
        let forest = start_cuts_opti::find_cuts_start(&dfg, &acts, &starts, &ends);
        let rendered: Vec<String> = forest.iter().map(render).collect();
        if rendered.len() == 1 { println!("{}", rendered[0]); } else { println!("forest({})", rendered.join(",")); }
    }
}
