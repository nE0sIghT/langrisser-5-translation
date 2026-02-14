#!/usr/bin/env python3
import csv
from pathlib import Path

ROWS = [
    {
        'chunk_index': 56,
        'record_index': 22,
        'fb00_label': '0017',
        'jp_text': 'ギザロフ様。',
        'confidence': 'high',
        'evidence': 'Direct token decode with confirmed mapping 02B0->様 and screenshot anchor match',
    },
    {
        'chunk_index': 56,
        'record_index': 23,
        'fb00_label': '0018',
        'jp_text': '素体の育成準備が整いました。',
        'confidence': 'medium',
        'evidence': 'Screenshot sequence immediately after rec22; record is short tokenized command-text style',
    },
    {
        'chunk_index': 56,
        'record_index': 24,
        'fb00_label': '0019',
        'jp_text': '手順通り、項目を読み上げますので、指示を願います。',
        'confidence': 'medium',
        'evidence': 'Screenshot sequence line after rec23 in same tutorial block',
    },
    {
        'chunk_index': 56,
        'record_index': 26,
        'fb00_label': '001B',
        'jp_text': 'まず最終成長形態の設定を行います。',
        'confidence': 'medium',
        'evidence': 'Order-based mapping from screenshot timeline and adjacent tutorial records',
    },
    {
        'chunk_index': 56,
        'record_index': 27,
        'fb00_label': '001C',
        'jp_text': '４つの金属の中から、３つを培養液に混ぜ合わせます。|不要な物を選んで下さい。',
        'confidence': 'medium',
        'evidence': 'Record has two text windows consistent with two-sentence screenshot',
    },
]


def main() -> None:
    out = Path('work/scen_analysis/confirmed_tutorial_subset.csv')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=['chunk_index', 'record_index', 'fb00_label', 'jp_text', 'confidence', 'evidence'],
        )
        w.writeheader()
        w.writerows(ROWS)
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
