def check_keys(obj, *expected_keys):
  '''
  Check if *expected_keys (nested) exists in `obj` (dict).
  '''
  if not isinstance(obj, dict):
    raise AttributeError('check_keys() expects dict as first argument.')
  if len(expected_keys) == 0:
      raise AttributeError('check_keys() expects at least two arguments, one given.')

  _obj = obj
  for expected_key in expected_keys:
    if expected_key in _obj:
      _obj = _obj[expected_key]
    else:
      return False

  return True

