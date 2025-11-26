DIFF_RUST = '''
```rust
### src/build.rs
<<<<<<< SEARCH
fn main() {
    let version = "1.0";
}
=======
fn main() {
    let version = "2.0";
}
>>>>>>> REPLACE
```
'''
