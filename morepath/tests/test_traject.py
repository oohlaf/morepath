
from reg import Lookup, ChainClassLookup
from morepath.app import App, global_app
from morepath.error import TrajectError
from morepath import generic
from morepath.pathstack import parse_path, DEFAULT
from morepath.request import Request
from morepath.traject import (is_identifier,
                              parse_variables,
                              interpolation_path,
                              VariableMatcher,
                              Traject, traject_consumer,
                              register_root, register_model)
from morepath.setup import setup
from werkzeug.test import EnvironBuilder
import py.test


def get_request(*args, **kw):
    return Request(EnvironBuilder(*args, **kw).get_environ())


class Root(object):
    pass


class Model(object):
    pass


class Special(object):
    pass


def test_identifier():
    assert is_identifier('a')
    not is_identifier('')
    assert is_identifier('a1')
    assert not is_identifier('1')
    assert is_identifier('_')
    assert is_identifier('_foo')
    assert is_identifier('foo')
    assert not is_identifier('.')


def test_parse_variables():
    assert parse_variables('No variables') == []
    assert parse_variables('The {foo} is the {bar}.') == ['foo', 'bar']
    assert parse_variables('{}') == ['']


def test_variable_matcher():
    matcher = VariableMatcher((DEFAULT, '{foo}'))
    assert matcher((DEFAULT, 'test')) == {'foo': 'test'}
    matcher = VariableMatcher((DEFAULT, 'foo-{n}'))
    assert matcher((DEFAULT, 'foo-bar')) == {'n': 'bar'}
    matcher = VariableMatcher((DEFAULT, 'hey'))
    assert matcher((DEFAULT, 'hey')) == {}
    matcher = VariableMatcher((DEFAULT, 'foo-{n}'))
    assert matcher((DEFAULT, 'blah')) == {}
    matcher = VariableMatcher((DEFAULT, '{ foo }'))
    assert matcher((DEFAULT, 'test')) == {'foo': 'test'}


def test_variable_matcher_ns():
    matcher = VariableMatcher((DEFAULT, '{foo}'))
    assert matcher(('not default', 'test')) == {}


def test_variable_matcher_checks():
    with py.test.raises(TrajectError):
        VariableMatcher((DEFAULT, '{1illegal}'))
    with py.test.raises(TrajectError):
        VariableMatcher((DEFAULT, '{}'))


def test_variable_matcher_type():
    matcher = VariableMatcher((DEFAULT, '{foo:str}'))
    assert matcher((DEFAULT, 'test')) == {'foo': 'test'}
    matcher = VariableMatcher((DEFAULT, '{foo:int}'))
    assert matcher((DEFAULT, '1')) == {'foo': 1}
    assert matcher((DEFAULT, 'noint')) == {}


def test_traject_consumer():
    app = App()
    traject = Traject()
    traject.register('sub', Model)
    app.register(generic.traject, [App], lambda base: traject)
    found, obj, stack = traject_consumer(app, parse_path('sub'), Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []


def test_traject_consumer_not_found():
    app = App()
    found, obj, stack = traject_consumer(app, parse_path('sub'), Lookup(app))
    assert not found
    assert obj is app
    assert stack == [(u'default', 'sub')]


def test_traject_consumer_factory_returns_none():
    app = App()

    traject = Traject()

    def get_model():
        return None

    traject.register('sub', get_model)
    app.register(generic.traject, [App], lambda base: traject)

    found, obj, stack = traject_consumer(app, parse_path('sub'), Lookup(app))
    assert not found
    assert obj is app
    assert stack == [(u'default', 'sub')]


def test_traject_consumer_variable():
    app = App()

    traject = Traject()

    def get_model(foo):
        result = Model()
        result.foo = foo
        return result

    traject.register('{foo}', get_model)
    app.register(generic.traject, [App], lambda base: traject)

    found, obj, stack = traject_consumer(app, parse_path('something'),
                                         Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []
    assert obj.foo == 'something'


def test_traject_consumer_combination():
    app = App()

    traject = Traject()

    def get_model(foo):
        result = Model()
        result.foo = foo
        return result

    traject.register('special', Special)
    traject.register('{foo}', get_model)
    app.register(generic.traject, [App], lambda base: traject)

    found, obj, stack = traject_consumer(app, parse_path('something'),
                                         Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []
    assert obj.foo == 'something'
    found, obj, stack = traject_consumer(app, parse_path('special'),
                                         Lookup(app))
    assert found
    assert isinstance(obj, Special)
    assert stack == []


def test_traject_nested():
    app = App()

    traject = Traject()
    traject.register('a', Model)
    traject.register('a/b', Special)
    app.register(generic.traject, [App], lambda base: traject)

    found, obj, stack = traject_consumer(app, parse_path('a'), Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []
    found, obj, stack = traject_consumer(app, parse_path('a/b'), Lookup(app))
    assert found
    assert isinstance(obj, Special)
    assert stack == []


def test_traject_nested_not_resolved_entirely_by_consumer():
    app = App()
    traject = Traject()
    traject.register('a', Model)
    app.register(generic.traject, [App], lambda base: traject)

    found, obj, stack = traject_consumer(app, parse_path('a'), Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []
    found, obj, stack = traject_consumer(app, parse_path('a/b'), Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == [('default', 'b')]


def test_traject_nested_with_variable():
    app = App()

    traject = Traject()

    def get_model(id):
        result = Model()
        result.id = id
        return result

    def get_special(id):
        result = Special()
        result.id = id
        return result

    traject.register('{id}', get_model)
    traject.register('{id}/sub', get_special)
    app.register(generic.traject, [App], lambda base: traject)

    found, obj, stack = traject_consumer(app, parse_path('a'), Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []
    found, obj, stack = traject_consumer(app, parse_path('b'), Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []
    found, obj, stack = traject_consumer(app, parse_path('a/sub'), Lookup(app))
    assert found
    assert isinstance(obj, Special)
    assert stack == []


def test_traject_with_multiple_variables():
    app = App()

    traject = Traject()

    def get_model(first_id):
        result = Model()
        result.first_id = first_id
        return result

    def get_special(first_id, second_id):
        result = Special()
        result.first_id = first_id
        result.second_id = second_id
        return result
    traject.register('{first_id}', get_model)
    traject.register('{first_id}/{second_id}', get_special)
    app.register(generic.traject, [App], lambda base: traject)

    found, obj, stack = traject_consumer(app, parse_path('a'), Lookup(app))
    assert found
    assert isinstance(obj, Model)
    assert stack == []
    assert obj.first_id == 'a'
    assert not hasattr(obj, 'second_id')
    found, obj, stack = traject_consumer(app, parse_path('a/b'), Lookup(app))
    assert found
    assert isinstance(obj, Special)
    assert stack == []
    assert obj.first_id == 'a'
    assert obj.second_id == 'b'


def test_traject_no_concecutive_variables():
    traject = Traject()

    def get_model(foo, bar):
        return Model()

    with py.test.raises(TrajectError):
        traject.register('{foo}{bar}', get_model)


def test_traject_no_duplicate_variables():
    traject = Traject()

    def get_model(foo):
        return Model

    with py.test.raises(TrajectError):
        traject.register('{foo}-{foo}', get_model)
    with py.test.raises(TrajectError):
        traject.register('{foo}/{foo}', get_model)


def test_traject_conflicting_registrations():
    traject = Traject()

    def get_model(foo):
        return Model

    traject.register('{foo}', get_model)
    with py.test.raises(TrajectError):
        traject.register('{bar}', get_model)


def test_traject_conflicting_registrations_without_variables():
    traject = Traject()

    def get_model(foo):
        return Model()

    def get_model2(foo):
        return Model()

    traject.register('foo', get_model)
    with py.test.raises(TrajectError):
        traject.register('foo', get_model2)


def test_traject_conflicting_type_registrations():
    traject = Traject()

    def get_model(foo):
        return Model()

    traject.register('{foo:str}', get_model)
    with py.test.raises(TrajectError):
        traject.register('{foo:int}', get_model)


def test_traject_no_conflict_if_different_path():
    traject = Traject()

    def get_model(foo):
        return Model()

    traject.register('a/{foo}', get_model)
    traject.register('b/{bar}', get_model)
    assert True


def test_traject_conflict_if_same_path():
    traject = Traject()

    def get_model(foo):
        return Model()

    traject.register('a/{foo}', get_model)
    with py.test.raises(TrajectError):
        traject.register('a/{bar}', get_model)
    assert True


def test_traject_no_conflict_if_different_text():
    traject = Traject()

    def get_model(foo):
        return Model()

    traject.register('prefix-{foo}', get_model)
    traject.register('{foo}-postfix', get_model)
    assert True


def test_interpolation_path():
    assert interpolation_path('{foo} is {bar}') == '%(foo)s is %(bar)s'


def test_path_for_model():
    traject = Traject()

    class IdModel(object):
        def __init__(self, id):
            self.id = id

    traject.register_inverse(IdModel, 'foo/{id}',
                             lambda model: {'id': model.id})
    assert traject.get_path(IdModel('a')) == 'foo/a'


def test_register_root():
    app = App()
    root = Root()
    app.root_model = Root
    app.root_obj = root
    lookup = Lookup(ChainClassLookup(app, global_app))

    register_root(app, Root, lambda: root)
    request = get_request()
    request.lookup = lookup
    assert generic.path(request, root, lookup=lookup) == ''
    assert generic.base(root, lookup=lookup) is app


def test_register_model():
    setup()
    app = App()
    root = Root()
    app.root_model = Root
    app.root_obj = root
    lookup = Lookup(ChainClassLookup(app, global_app))

    def get_model(id):
        model = Model()
        model.id = id
        return model

    register_root(app, Root, lambda: root)
    register_model(app, Model, '{id}', lambda model: {'id': model.id},
                   get_model)

    found, obj, stack = traject_consumer(app, parse_path('a'), lookup)
    assert obj.id == 'a'
    model = Model()
    model.id = 'b'
    request = get_request()
    request.lookup = lookup
    assert generic.path(request, model, lookup=lookup) == 'b'
    assert generic.base(model, lookup=lookup) is app


def test_traject_path_with_leading_slash():
    setup()
    app = App()
    root = Root()
    app.root_model = Root
    app.root_obj = root
    lookup = Lookup(ChainClassLookup(app, global_app))

    def get_model(id):
        model = Model()
        model.id = id
        return model

    register_root(app, Root, lambda: root)
    register_model(app, Model, '/foo/{id}', lambda model: {'id': model.id},
                   get_model)
    found, obj, stack = traject_consumer(app, parse_path('foo/a'), lookup)
    assert obj.id == 'a'
    found, obj, stack = traject_consumer(app, parse_path('/foo/a'), lookup)
    assert obj.id == 'a'


# XXX we still need to do a conflict between a model path and an app name

# def test_conflict_app_and_model():
#     reg = Registry()
#     def get_model(id):
#         model = Model()
#         model.id = id
#         return model
#     def get_app():
#         return App()
#     register_model(reg, Root, Model, 'a/{id}',
#                    lambda model: {'id': model.id},
#                    get_model)
#     with py.test.raises(TrajectError):
#         register_app(reg, Root, App, 'a', get_app)

# def test_conflict_model_and_app():
#     reg = Registry()
#     def get_model(id):
#         model = Model()
#         model.id = id
#         return model
#     def get_app():
#         return App()
#     register_app(reg, Root, App, 'a', get_app)
#     with py.test.raises(TrajectError):
#         register_model(reg, Root, Model, 'a/{id}',
#                        lambda model: { 'id': model.id},
#                        get_model)
