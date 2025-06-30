#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skrypt do porównania i interaktywnego łączenia plików LookML View.
Autor: Assistant
Wersja: 3.5.1
Data: 2025-06-30
"""

import os
import re
import sys
import shutil
from pathlib import Path
from collections import defaultdict
import html # Dodano import modułu html

# --- Funkcje z v3.x (rdzeń interaktywny i parser) ---

def parse_lookml_file(file_path):
    """
    Parsuje plik LookML, ekstraktując elementy, ich właściwości oraz surowy blok kodu.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    elements = {
        'dimensions': {},
        'measures': {},
        'dimension_groups': {},
        'sets': {},
        'drills': {}
    }

    patterns = {
        'dimension': r'(dimension:\s*(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\})',
        'measure': r'(measure:\s*(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\})',
        'dimension_group': r'(dimension_group:\s*(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\})',
        'set': r'(set:\s*(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\})',
        'drill': r'(drill:\s*(\w+)\s*\{([\s\S]*?)\})'
    }

    for element_type, pattern in patterns.items():
        for match in re.finditer(pattern, content, re.DOTALL):
            raw_block, name, body = match.group(1), match.group(2), match.group(3)
            properties = extract_properties(body)
            key = 'dimension_groups' if element_type == 'dimension_group' else element_type + 's'
            elements[key][name] = {'properties': properties, 'raw_block': raw_block.strip()}
    return elements

def extract_properties(body):
    """
    Ekstraktuje właściwości z ciała elementu LookML.
    """
    properties = {}
    property_patterns = {
        'type': r'type:\s*([^\n\r]+)',
        'sql': r'sql:\s*([^;]+);?',
        'label': r'label:\s*"([^"]*)"',
        'description': r'description:\s*"([^"]*)"',
        'hidden': r'hidden:\s*(\w+)',
        'primary_key': r'primary_key:\s*(\w+)',
        'timeframes': r'timeframes:\s*\[([^\]]+)\]',
        'convert_tz': r'convert_tz:\s*(\w+)',
        'datatype': r'datatype:\s*(\w+)',
        'value_format': r'value_format:\s*"([^"]*)"',
        'drill_fields': r'drill_fields:\s*\[([^\]]*)\]',
        'fields': r'fields:\s*\[([^\]]*)\]',
        'url': r'url:\s*"([^"]*)"'
    }
    for prop_name, pattern in property_patterns.items():
        match = re.search(pattern, body, re.DOTALL)
        if match:
            properties[prop_name] = match.group(1).strip()
    return properties

def get_lookml_files(folder_path):
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"Błąd: Ścieżka {folder_path} nie jest folderem lub nie istnieje.")
        return {}
    return {f.name: f for f in folder.glob("*.view.lkml")}

def compare_lookml_folders(folder_old, folder_new):
    old_files, new_files = get_lookml_files(folder_old), get_lookml_files(folder_new)
    comparison_results = {}
    common_files = set(old_files.keys()) & set(new_files.keys())

    for filename in sorted(common_files):
        old_path, new_path = old_files[filename], new_files[filename]
        try:
            old_parsed, new_parsed, changes = compare_files(old_path, new_path)
            comparison_results[filename] = {
                'changes': changes,
                'old_elements_parsed': old_parsed,
                'new_elements_parsed': new_parsed,
                'old_path': old_path,
                'new_path': new_path # Dodano new_path do comparison_results
            }
        except Exception as e:
            print(f"Błąd podczas porównywania pliku {filename}: {e}")

    missing_in_new = set(old_files.keys()) - set(new_files.keys())
    missing_in_old = set(new_files.keys()) - set(old_files.keys())
    return comparison_results, missing_in_new, missing_in_old

def compare_files(old_file_path, new_file_path):
    old_elements = parse_lookml_file(old_file_path)
    new_elements = parse_lookml_file(new_file_path)
    all_changes = {}
    for element_type in ['dimensions', 'measures', 'dimension_groups', 'sets', 'drills']:
        changes = compare_elements(old_elements, new_elements, element_type)
        if any(changes.values()):
            all_changes[element_type] = changes
    return old_elements, new_elements, all_changes

def compare_elements(old_elements, new_elements, element_type):
    changes = {'dodane': {}, 'usuniete': {}, 'zmienione': {}}
    old_names = set(old_elements.get(element_type, {}).keys())
    new_names = set(new_elements.get(element_type, {}).keys())

    for name in new_names - old_names:
        changes['dodane'][name] = new_elements[element_type][name]
    for name in old_names - new_names:
        changes['usuniete'][name] = old_elements[element_type][name]
    for name in old_names & new_names:
        old_props = old_elements[element_type][name]['properties']
        new_props = new_elements[element_type][name]['properties']
        if old_props != new_props:
            changes['zmienione'][name] = {'stare': old_elements[element_type][name], 'nowe': new_elements[element_type][name]}
    return changes

def setup_merge_directory(merge_folder_path, source_folder_path):
    merge_path, source_path = Path(merge_folder_path), Path(source_folder_path)
    if merge_path.exists():
        shutil.rmtree(merge_path)
    shutil.copytree(source_path, merge_path)
    print(f"Skopiowano pliki z {source_path} do {merge_path}")

def apply_change_to_file(target_file_path, change_type, element_name, old_element_data, new_element_data, original_old_path=None, original_new_path=None):
    """Aplikuje pojedynczą, zaakceptowaną przez użytkownika zmianę do pliku w folderze 'merge'."""
    try:
        if change_type == 'plik_usuniete': # Cały plik usunięty (przywracamy)
            shutil.copy(original_old_path, target_file_path)
            print(f"  -> ZASTOSOWANO: Przywrócono plik {element_name} z wersji 'old'.")
            return
        elif change_type == 'plik_dodane': # Cały plik dodany (usuwamy)
            os.remove(target_file_path)
            print(f"  -> ZASTOSOWANO: Usunięto plik {element_name} z wersji 'new'.")
            return

        with open(target_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if change_type == 'zmienione_typ': # Zmiana typu elementu
            content = content.replace(new_element_data['raw_block'], old_element_data['raw_block'])
            print(f"  -> ZASTOSOWANO: Przywrócono '{element_name}' z wersji 'old' (zmiana typu).")
        elif change_type == 'dodane':
            content = content.replace(new_element_data['raw_block'], '')
            print(f"  -> ZASTOSOWANO: Usunięto dodany element '{element_name}'.")
        elif change_type == 'usuniete':
            content += f"\n\n{old_element_data['raw_block']}"
            print(f"  -> ZASTOSOWANO: Przywrócono usunięty element '{element_name}'.")
        elif change_type == 'zmienione_atrybut':
            singular_et = new_element_data['element_type'][:-1] 
            attribute = new_element_data['attribute']
            old_value = old_element_data 
            new_value = new_element_data['value'] 

            element_pattern = re.compile(f"({singular_et}:\s*{element_name}\s*\{{[\s\S]*?\}})", re.DOTALL)
            match = element_pattern.search(content)
            if not match:
                print(f"  -> BŁĄD: Nie znaleziono bloku dla '{element_name}'.")
                return

            element_block = match.group(1)
            patterns = {
                'default': (re.compile(f'({attribute}:\s*)"[^"]*"(\s*)'), f'\g<1>"{old_value}"\g<2>'),
                'unquoted': (re.compile(f'({attribute}:\s*)[^\n\r]+(\s*)'), f'\g<1>{old_value}\g<2>'),
                'list': (re.compile(f'({attribute}:\s*\[)[^\]]*(\])'), f'\g<1>{old_value}\g<2>')
            }
            
            if attribute in ['label', 'description', 'value_format', 'url']:
                pattern, replacement = patterns['default']
            elif attribute in ['timeframes', 'drill_fields', 'fields']:
                pattern, replacement = patterns['list']
            else:
                pattern, replacement = patterns['unquoted']

            new_element_block, count = pattern.subn(replacement, element_block)
            if count == 0:
                print(f"  -> BŁĄD: Nie udało się podmienić atrybutu '{attribute}' w '{element_name}'.")
                return

            content = content.replace(element_block, new_element_block)
            print(f"  -> ZASTOSOWANO: Zmieniono '{attribute}' w '{element_name}'.")

        with open(target_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    except Exception as e:
        print(f"  -> BŁĄD podczas zapisu zmiany dla '{element_name}': {e}")

def _get_all_changes_as_list(comparison_results, missing_in_new, missing_in_old):
    all_changes_list = []
    
    # Dodane/Usunięte pliki
    for filename in sorted(missing_in_new):
        all_changes_list.append({
            'filename': filename,
            'element_name': filename,
            'element_type': 'plik',
            'change_type': 'USUNIĘTE',
            'attribute': 'cały plik',
            'old_value': 'istniał',
            'new_value': '-',
            'raw_old_data': None, # Nie dotyczy
            'raw_new_data': None, # Nie dotyczy
            'action_type': 'plik_usuniete',
            'original_old_path': Path("folder_old") / filename, # Ścieżka do oryginalnego pliku
            'original_new_path': None
        })
    for filename in sorted(missing_in_old):
        all_changes_list.append({
            'filename': filename,
            'element_name': filename,
            'element_type': 'plik',
            'change_type': 'DODANE',
            'attribute': 'cały plik',
            'old_value': '-',
            'new_value': 'istnieje',
            'raw_old_data': None,
            'raw_new_data': None,
            'action_type': 'plik_dodane',
            'original_old_path': None,
            'original_new_path': Path("folder_new") / filename # Ścieżka do oryginalnego pliku
        })

    for filename, result in sorted(comparison_results.items()):
        old_elements_parsed = result['old_elements_parsed']
        new_elements_parsed = result['new_elements_parsed']
        changes = result['changes']
        
        processed_elements = set() # Zbiór elementów już przetworzonych (np. zmiana typu)

        # Krok 1: Zmiany typu elementu
        all_element_names = set(k for et in old_elements_parsed.values() for k in et) | set(k for et in new_elements_parsed.values() for k in et)
        for name in sorted(list(all_element_names)):
            old_type = next((et for et, elements in old_elements_parsed.items() if name in elements), None)
            new_type = next((et for et, elements in new_elements_parsed.items() if name in elements), None)

            if old_type and new_type and old_type != new_type:
                all_changes_list.append({
                    'filename': filename,
                    'element_name': name,
                    'element_type': 'rodzaj',
                    'change_type': 'ZMIENIONE',
                    'attribute': 'typ',
                    'old_value': old_type[:-1],
                    'new_value': new_type[:-1],
                    'raw_old_data': old_elements_parsed[old_type][name],
                    'raw_new_data': new_elements_parsed[new_type][name],
                    'action_type': 'zmienione_typ'
                })
                processed_elements.add(name)

        # Krok 2: Dodane i usunięte elementy (wspólne pliki)
        for element_type, type_changes in changes.items():
            singular_et = element_type[:-1]
            for name, data in type_changes.get('dodane', {}).items():
                if name in processed_elements: continue
                all_changes_list.append({
                    'filename': filename,
                    'element_name': name,
                    'element_type': singular_et,
                    'change_type': 'DODANE',
                    'attribute': 'cały element',
                    'old_value': '-',
                    'new_value': 'istnieje',
                    'raw_old_data': None,
                    'raw_new_data': data,
                    'action_type': 'dodane'
                })
                processed_elements.add(name)

            for name, data in type_changes.get('usuniete', {}).items():
                if name in processed_elements: continue
                all_changes_list.append({
                    'filename': filename,
                    'element_name': name,
                    'element_type': singular_et,
                    'change_type': 'USUNIĘTE',
                    'attribute': 'cały element',
                    'old_value': 'istniał',
                    'new_value': '-',
                    'raw_old_data': data,
                    'raw_new_data': None,
                    'action_type': 'usuniete'
                })
                processed_elements.add(name)

        # Krok 3: Zmienione atrybuty
        for element_type, type_changes in changes.items():
            singular_et = element_type[:-1]
            for name, data in type_changes.get('zmienione', {}).items():
                if name in processed_elements: continue
                old_props = data['stare']['properties']
                new_props = data['nowe']['properties']
                all_keys = set(old_props.keys()) | set(new_props.keys())
                for key in sorted(list(all_keys)):
                    old_val, new_val = old_props.get(key, '[BRAK]'), new_props.get(key, '[BRAK]')
                    if old_val != new_val:
                        all_changes_list.append({
                            'filename': filename,
                            'element_name': name,
                            'element_type': singular_et,
                            'change_type': 'ZMIENIONE',
                            'attribute': key,
                            'old_value': old_val,
                            'new_value': new_val,
                            'raw_old_data': old_val, # Dla atrybutów, raw_old_data to sama wartość
                            'raw_new_data': {'value': new_val, 'element_type': element_type, 'attribute': key},
                            'action_type': 'zmienione_atrybut'
                        })
    return all_changes_list

def interactive_merge_changes(comparison_results, merge_folder, missing_in_new, missing_in_old):
    print("\nRozpoczynanie szczegółowego interaktywnego łączenia... (t/n)")
    
    all_changes_to_process = _get_all_changes_as_list(comparison_results, missing_in_new, missing_in_old)

    for change_info in all_changes_to_process:
        filename = change_info['filename']
        element_name = change_info['element_name']
        element_type = change_info['element_type']
        change_type = change_info['change_type']
        attribute = change_info['attribute']
        old_value = change_info['old_value']
        new_value = change_info['new_value']
        raw_old_data = change_info['raw_old_data']
        raw_new_data = change_info['raw_new_data']
        action_type = change_info['action_type']
        original_old_path = change_info.get('original_old_path')
        original_new_path = change_info.get('original_new_path')

        print(f"\n--- Plik: {filename} ---")
        print(f"Element: {element_name} ({element_type})")
        print(f"Rodzaj zmiany: {change_type}")
        print(f"Atrybut: {attribute}")
        print(f"Stara wartość: {old_value}")
        print(f"Nowa wartość:  {new_value}")

        decision = input("  Czy chcesz cofnąć tę zmianę (przywrócić starą wersję)? (t/n): ").lower().strip()
        if decision == 't':
            apply_change_to_file(Path(merge_folder) / filename, action_type, element_name, raw_old_data, raw_new_data, original_old_path, original_new_path)
        else:
            print("  -> POMINIĘTO.")

def run_interactive_comparison_and_merge(folder_old, folder_new, folder_merge):
    print("🚀 URUCHAMIANIE PORÓWNANIA I INTERAKTYWNEGO ŁĄCZENIA")
    comparison_results, missing_in_new, missing_in_old = compare_lookml_folders(folder_old, folder_new)
    if not comparison_results and not missing_in_new and not missing_in_old:
        print("\n✅ Brak zmian do scalenia. Foldery są zgodne.")
        return
    setup_merge_directory(folder_merge, folder_new)
    interactive_merge_changes(comparison_results, folder_merge, missing_in_new, missing_in_old)
    print("\n\n✅ PROCES ŁĄCZENIA ZAKOŃCZONY!")

# --- Funkcje raportujące (logika z v2.6.0) ---

def _transform_results_for_legacy_reporting(comparison_results):
    """Konwertuje wyniki z nowej struktury do starej, oczekiwanej przez funkcje z v2.6.0."""
    legacy_results = {}
    for filename, result in comparison_results.items():
        legacy_results[filename] = {
            'changes': {et: {k: v for k, v in tc.items()} for et, tc in result['changes'].items()},
            'old_elements_parsed': {et: {k: v['properties'] for k, v in p.items()} for et, p in result['old_elements_parsed'].items()},
            'new_elements_parsed': {et: {k: v['properties'] for k, v in p.items()} for et, p in result['new_elements_parsed'].items()}
        }
        for et, tc in legacy_results[filename]['changes'].items():
            if 'zmienione' in tc:
                for name, change_data in tc['zmienione'].items():
                    tc['zmienione'][name] = {
                        'stare': change_data['stare']['properties'],
                        'nowe': change_data['nowe']['properties']
                    }
    return legacy_results

def generate_consolidated_report(comparison_results, missing_in_new, missing_in_old):
    print(f"\n{'='*120}")
    print(f"PODSUMOWANIE ZMIAN W PLIKACH LOOKML")
    print(f"{'='*120}")
    headers = ["Plik", "Element", "Rodzaj", "Zmiana", "Atrybut", "Stara wartość", "Nowa wartość"]
    print(f"{headers[0]:<25} | {headers[1]:<20} | {headers[2]:<15} | {headers[3]:<12} | {headers[4]:<15} | {headers[5]:<25} | {headers[6]:<25}")
    print("-" * 150)
    rows = []
    for filename, result in sorted(comparison_results.items()):
        old_elements_parsed = result['old_elements_parsed']
        new_elements_parsed = result['new_elements_parsed']
        type_changed_elements = set()
        for name in sorted(list(set(k for et in old_elements_parsed.values() for k in et) | set(k for et in new_elements_parsed.values() for k in et))):
            old_type = next((et[:-1] for et, elements in old_elements_parsed.items() if name in elements), None)
            new_type = next((et[:-1] for et, elements in new_elements_parsed.items() if name in elements), None)
            if old_type and new_type and old_type != new_type:
                rows.append((filename, name, "rodzaj", "ZMIENIONE", "typ", old_type, new_type))
                type_changed_elements.add(name)
        changes = result['changes']
        for element_type, type_changes in changes.items():
            singular_et = element_type[:-1]
            for name, props in type_changes.get('dodane', {}).items():
                if name not in type_changed_elements: rows.append((filename, name, singular_et, "DODANE", "cały element", "-", "istnieje"))
            for name, props in type_changes.get('usuniete', {}).items():
                if name not in type_changed_elements: rows.append((filename, name, singular_et, "USUNIĘTE", "cały element", "istniał", "-"))
            for name, change_info in type_changes.get('zmienione', {}).items():
                if name in type_changed_elements: continue
                old_props, new_props = change_info['stare'], change_info['nowe']
                for key in set(old_props.keys()) | set(new_props.keys()):
                    old_val, new_val = old_props.get(key, '[BRAK]'), new_props.get(key, '[BRAK]')
                    if old_val != new_val: rows.append((filename, name, singular_et, "ZMIENIONE", key, old_val, new_val))
    for row in sorted(rows, key=lambda x: (x[0], x[1])):
        print(f"{row[0]:<25} | {row[1]:<20} | {row[2]:<15} | {row[3]:<12} | {row[4]:<15} | {str(row[5]):<25} | {str(row[6]):<25}")
    if missing_in_new: print("\nPLIKI USUNIĘTE:", sorted(missing_in_new))
    if missing_in_old: print("\nPLIKI NOWE:", sorted(missing_in_old))

def generate_html_table_report(comparison_results, missing_in_new, missing_in_old, output_file="lookml_comparison_table_report.html"):
    headers = ["Plik", "Element", "Rodzaj", "Zmiana", "Atrybut", "Stara wartość", "Nowa wartość"]
    rows = []
    for filename, result in sorted(comparison_results.items()):
        old_elements_parsed = result['old_elements_parsed']
        new_elements_parsed = result['new_elements_parsed']
        type_changed_elements = set()
        for name in sorted(list(set(k for et in old_elements_parsed.values() for k in et) | set(k for et in new_elements_parsed.values() for k in et))):
            old_type = next((et[:-1] for et, elements in old_elements_parsed.items() if name in elements), None)
            new_type = next((et[:-1] for et, elements in new_elements_parsed.items() if name in elements), None)
            if old_type and new_type and old_type != new_type:
                rows.append((filename, name, "rodzaj", "ZMIENIONE", "typ", old_type, new_type))
                type_changed_elements.add(name)
        changes = result['changes']
        for element_type, type_changes in changes.items():
            singular_et = element_type[:-1]
            for name, props in type_changes.get('dodane', {}).items():
                if name not in type_changed_elements: rows.append((filename, name, singular_et, "DODANE", "cały element", "-", "istnieje"))
            for name, props in type_changes.get('usuniete', {}).items():
                if name not in type_changed_elements: rows.append((filename, name, singular_et, "USUNIĘTE", "cały element", "istniał", "-"))
            for name, change_info in type_changes.get('zmienione', {}).items():
                if name in type_changed_elements: continue
                old_props, new_props = change_info['stare'], change_info['nowe']
                for key in set(old_props.keys()) | set(new_props.keys()):
                    old_val, new_val = old_props.get(key, '[BRAK]'), new_props.get(key, '[BRAK]')
                    if old_val != new_val: rows.append((filename, name, singular_et, "ZMIENIONE", key, old_val, new_val))
    html_content = """
    <!DOCTYPE html><html><head><title>LookML Comparison Table Report</title><style>body{{font-family:Arial,sans-serif;margin:20px}}table{{width:100%;border-collapse:collapse;margin-bottom:20px;table-layout:fixed}}th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top;word-wrap:break-word}}th{{background-color:#f2f2f2}}.long-text{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}}.long-text:hover{{overflow:visible;white-space:normal;height:auto;position:absolute;background-color:#fff;border:1px solid #ccc;z-index:1;box-shadow:2px 2px 5px rgba(0,0,0,.2);max-width:500px}}ul{{list-style-type:none;padding:0}}li{{margin-bottom:5px}}</style></head><body>
    <h1>LookML Comparison Table Report</h1><h2>Summary of Changes</h2><table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>
    <h2>Files Missing in New Folder</h2><ul>{missing_new}</ul><h2>New Files in New Folder</h2><ul>{missing_old}</ul></body></html>
    """.format(
        th="".join([f"<th>{h}</th>" for h in headers]),
        tbody = "".join([
            "<tr>" + " ".join([
            f'<td class="long-text" title="{html.escape(str(c))}">{html.escape(str(c))}</td>'
            for c in r
            ]) + "</tr>"
            for r in sorted(rows, key=lambda x: (x[0], x[1]))
        ]),
        missing_new="".join([f"<li>{f}</li>" for f in sorted(missing_in_new)]),
        missing_old="".join([f"<li>{f}</li>" for f in sorted(missing_in_old)])
    )
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Wygenerowano raport HTML: {output_file}")

def run_complete_comparison(folder_old, folder_new, html_table=False):
    print("🚀 URUCHAMIANIE PORÓWNANIA LOOKML (STYL v2.6.0)")
    comparison_results, missing_in_new, missing_in_old = compare_lookml_folders(folder_old, folder_new)
    
    legacy_results = _transform_results_for_legacy_reporting(comparison_results)
    
    generate_consolidated_report(legacy_results, missing_in_new, missing_in_old)
    if html_table:
        generate_html_table_report(legacy_results, missing_in_new, missing_in_old)

if __name__ == "__main__":
    current_dir = Path(__file__).parent
    folder_old = current_dir / "folder_old"
    folder_new = current_dir / "folder_new"
    folder_merge = current_dir / "merge"
    run_interactive_comparison_and_merge(folder_old, folder_new, folder_merge)
