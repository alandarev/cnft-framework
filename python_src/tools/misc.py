
def format_ada(lovelace):
    try:
        return '{0:.6f}'.format(int(lovelace) / 1000000.0)
    except:
        return 0
