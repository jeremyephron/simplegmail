from simplegmail import query

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
