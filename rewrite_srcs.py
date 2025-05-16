# /// script
# requires-python = ">=3.12"
# ///

import argparse
import html.parser
import pathlib
import sys
from typing import List, Set, Tuple


class ImageRewriter(html.parser.HTMLParser):
    """HTML parser that identifies and rewrites img tags with data-canonical-src attributes."""
    
    def __init__(self):
        super().__init__()
        self.result = []
        self.modified = False
        self.img_count = 0
        self.in_img = False
        self.current_attrs = None
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == "img" and "data-canonical-src" in attrs_dict:
            # This is an image tag with data-canonical-src
            self.in_img = True
            self.current_attrs = attrs_dict
            
            # Rewrite the attributes
            original_src = attrs_dict.get("src", "")
            canonical_src = attrs_dict["data-canonical-src"]
            
            # Create new attributes list with our modifications
            new_attrs = []
            for key, value in attrs:
                if key == "src":
                    # Replace src with data-canonical-src value
                    new_attrs.append((key, canonical_src))
                elif key == "data-canonical-src":
                    # Skip this, we'll remove it
                    continue
                else:
                    # Keep all other attributes unchanged
                    new_attrs.append((key, value))
            
            # Add the new data-camo-src attribute
            new_attrs.append(("data-camo-src", original_src))
            
            # Write the new tag with modified attributes
            attr_str = " ".join(f'{k}="{v}"' for k, v in new_attrs)
            self.result.append(f"<img {attr_str}>")
            
            self.modified = True
            self.img_count += 1
        else:
            # Not a target img tag, pass through unchanged
            attrs_str = " ".join(f'{k}="{v}"' for k, v in attrs)
            if attrs_str:
                self.result.append(f"<{tag} {attrs_str}>")
            else:
                self.result.append(f"<{tag}>")
    
    def handle_endtag(self, tag):
        if self.in_img and tag == "img":
            self.in_img = False
            self.current_attrs = None
        else:
            self.result.append(f"</{tag}>")
    
    def handle_data(self, data):
        self.result.append(data)
    
    def handle_comment(self, data):
        self.result.append(f"<!--{data}-->")
    
    def handle_entityref(self, name):
        self.result.append(f"&{name};")
    
    def handle_charref(self, name):
        self.result.append(f"&#{name};")
    
    def handle_decl(self, decl):
        self.result.append(f"<!{decl}>")
    
    def handle_pi(self, data):
        self.result.append(f"<?{data}>")
    
    def get_result(self) -> str:
        return "".join(self.result)


def process_html_file(file_path: pathlib.Path, dry_run: bool) -> Tuple[bool, int]:
    """Process a single HTML file, rewriting image tags as needed."""
    try:
        content = file_path.read_text(encoding="utf-8")
        
        # Parse and rewrite HTML
        parser = ImageRewriter()
        parser.feed(content)
        
        if parser.modified:
            if not dry_run:
                file_path.write_text(parser.get_result(), encoding="utf-8")
            print(f"Modified {file_path}: {parser.img_count} images rewritten")
            return True, parser.img_count
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
    
    return False, 0


def find_html_files(directory: pathlib.Path) -> List[pathlib.Path]:
    """Find all HTML files in the given directory and subdirectories."""
    return list(directory.glob("**/*.html"))


def main():
    parser = argparse.ArgumentParser(description=(
        "Scan a directory for HTML files and rewrite image tags to use canonical URLs. "
        "For each image with a data-canonical-src attribute, this script: "
        "1. Sets src to the value from data-canonical-src "
        "2. Adds data-camo-src with the original src value "
        "3. Removes the data-canonical-src attribute"
    ))
    parser.add_argument("directory", type=pathlib.Path, 
                       help="Directory to scan for HTML files")
    parser.add_argument("--dry-run", action="store_true",
                       help="Don't modify files, just show what would be changed")
    
    args = parser.parse_args()
    
    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        return 1
    
    html_files = find_html_files(args.directory)
    file_count = 0
    image_count = 0
    
    for html_file in html_files:
        modified, img_count = process_html_file(html_file, args.dry_run)
        if modified:
            file_count += 1
            image_count += img_count
    
    print(f"Summary: {image_count} images rewritten in {file_count} files")
    if args.dry_run:
        print("This was a dry run - no files were modified")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
