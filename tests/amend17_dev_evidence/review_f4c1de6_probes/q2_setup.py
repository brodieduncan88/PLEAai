import sys; W = sys.argv[1]; sys.path.insert(0, W); sys.path.insert(0, W + '/verify')
from plea_gateway import Store
import front_state
o = Store('postgresql://plea:plea@127.0.0.1:5432/plea_rv3'); o.init_schema(); o.init_authority(); front_state.install(o); print('installed')
