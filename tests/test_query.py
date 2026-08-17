import pytest

from simplegmail import query


BOOLEAN_TERMS = {
    'starred': 'is:starred',
    'snoozed': 'is:snoozed',
    'unread': 'is:unread',
    'read': 'is:read',
    'important': 'is:important',
    'attachment': 'has:attachment',
    'drive': 'has:drive',
    'docs': 'has:document',
    'sheets': 'has:spreadsheet',
    'slides': 'has:presentation',
}


class TestQuery(object):

    def test_and(self):
        _and = query._and

        expect = "(((a b c) (d e f)) ((g h i) j))"
        string = _and([
            _and([
                _and(['a', 'b', 'c']),
                _and(['d', 'e', 'f'])
            ]),
            _and([
                _and(['g', 'h', 'i']),
                'j'
            ])
        ])
        assert string == expect

    def test_or(self):
        _or = query._or

        expect = "{{{a b c} {d e f}} {{g h i} j}}"
        string = _or([
            _or([
                _or(['a', 'b', 'c']),
                _or(['d', 'e', 'f'])
            ]),
            _or([
                _or(['g', 'h', 'i']),
                'j'
            ])
        ])
        assert string == expect

    def test_exclude(self):
        _exclude = query._exclude

        expect = '-a'
        string = _exclude('a')
        assert string == expect

    def test_construct_query_from_keywords(self):
        expect = "({from:john@doe.com from:jane@doe.com} subject:meeting)"
        query_string = query.construct_query(
            sender=['john@doe.com', 'jane@doe.com'], subject='meeting'
        )
        assert query_string == expect

        expect = "(-is:starred (label:work label:HR))"
        query_string = query.construct_query(exclude_starred=True, 
                                             labels=['work', 'HR'])
        assert query_string == expect

        expect = "{(label:work label:HR) (label:wife label:house)}"
        query_string = query.construct_query(
            labels=[['work', 'HR'], ['wife', 'house']]
        )
        assert query_string == expect

    def test_construct_query_from_dicts(self):
        expect = "{(from:john@doe.com newer_than:1d {subject:meeting subject:HR}) (to:jane@doe.com CS AROUND 5 homework)}"
        query_string = query.construct_query(
            dict(
                sender='john@doe.com',
                newer_than=(1, 'day'),
                subject=['meeting', 'HR']
            ),
            dict(
                recipient='jane@doe.com',
                near_words=('CS', 'homework', 5)
            )
        )
        assert query_string == expect

    def test_boolean_terms_respect_their_values(self):
        for key, term in BOOLEAN_TERMS.items():
            assert query.construct_query(**{key: True}) == term
            assert query.construct_query(**{key: False}) == f'-{term}'

    def test_falsey_non_boolean_terms_are_not_negated(self):
        assert query.construct_query(subject='') == 'subject:'

    def test_date_terms_accept_unix_timestamps(self):
        query_string = query.construct_query(
            after=1692211200, before=1692211800
        )

        assert query_string == '(after:1692211200 before:1692211800)'

    def test_false_boolean_terms_in_or_queries_are_negated(self):
        query_string = query.construct_query(
            {'starred': False}, {'attachment': False}
        )
        assert query_string == '{-is:starred -has:attachment}'

    def test_false_boolean_terms_combine_with_other_terms(self):
        query_string = query.construct_query(
            sender='john@doe.com', starred=False, attachment=True
        )
        assert query_string == (
            '(from:john@doe.com -is:starred has:attachment)'
        )

    def test_exclude_prefix_still_negates_boolean_terms(self):
        assert query.construct_query(exclude_starred=True) == '-is:starred'
        assert query.construct_query(exclude_starred=False) == '-is:starred'

    def test_empty_query_is_empty(self):
        assert query.construct_query() == ''

    def test_rejects_mixed_query_styles(self):
        with pytest.raises(ValueError, match='either query dictionaries'):
            query.construct_query({'starred': True}, unread=True)

    def test_rejects_unknown_terms(self):
        with pytest.raises(ValueError, match='Unknown query term'):
            query.construct_query(unknown='value')

    @pytest.mark.parametrize(
        ('term', 'value'),
        [('starred', 'yes'), ('subject', True)],
    )
    def test_rejects_incorrect_boolean_values(self, term, value):
        with pytest.raises(ValueError, match='boolean'):
            query.construct_query(**{term: value})

    def test_rejects_invalid_relative_time_unit(self):
        with pytest.raises(ValueError, match='day, month, or year'):
            query.construct_query(newer_than=(1, 'week'))

    @pytest.mark.parametrize('value', [[], ()])
    def test_rejects_empty_sequence_values(self, value):
        with pytest.raises(ValueError, match='cannot be empty'):
            query.construct_query(labels=value)
