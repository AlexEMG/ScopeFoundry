from __future__ import absolute_import, print_function
from qtpy import QtCore, QtWidgets, QtGui
from ScopeFoundry.logged_quantity import LQCollection#, LoggedQuantity
from collections import OrderedDict
import pyqtgraph as pg
import warnings
from ScopeFoundry.helper_funcs import get_logger_from_class, QLock

class HardwareComponent(QtCore.QObject):
    """
    :class:`HardwareComponent`
    
    Base class for ScopeFoundry Hardware objects
    
    to subclass, implement :meth:`setup`, :meth:`connect` and :meth:`disconnect`
    
    """

    def add_logged_quantity(self, name, **kwargs):
        #lq = LoggedQuantity(name=name, **kwargs)
        #self.logged_quantities[name] = lq
        #return lq
        return self.settings.New(name, **kwargs)

    def add_operation(self, name, op_func):
        """
        Create an operation for the HardwareComponent.
        
        *op_func* is a function that will be called upon operation activation
        
        operations are typically exposed in the default ScopeFoundry gui via a pushButton
        
        :type name: str
        :type op_func: QtCore.Slot
        """
        
        self.operations[name] = op_func   
            
    def __init__(self, app, debug=False, name=None):
        """
        create new HardwareComponent attached to *app*
        """
        if not hasattr(self, 'name'):
            self.name = self.__class__.__name__

        if name is not None:
            self.name = name
            
                    
        QtCore.QObject.__init__(self)
        self.log = get_logger_from_class(self)

        # threading lock
        #self.lock = threading.Lock()
        #self.lock = DummyLock()
        self.lock = QLock(mode=0) # mode 0 is non-reentrant lock

        self.app = app

        #self.logged_quantities = OrderedDict()
        self.settings = LQCollection()
        self.operations = OrderedDict()

        self.connected = self.add_logged_quantity("connected", dtype=bool)
        self.connected.updated_value[bool].connect(self.enable_connection)

        self.connect_success = False

        
        self.debug_mode = self.add_logged_quantity("debug_mode", dtype=bool, initial=debug)
        
        self.auto_thread_lock = True
        
        self.setup()

        if self.auto_thread_lock:        
            self.thread_lock_all_lq()

        self.has_been_connected_once = False
        
        self.is_connected = False
        
    def setup(self):
        """
        Runs during __init__, before the hardware connection is established
        Should generate desired LoggedQuantities, operations
        """
        raise NotImplementedError()

    def new_control_widgets(self):
        
        self.controls_groupBox = QtWidgets.QGroupBox(self.name)
        self.controls_formLayout = QtWidgets.QFormLayout()
        self.controls_groupBox.setLayout(self.controls_formLayout)
                
        #self.connect_hardware_checkBox = QtWidgets.QCheckBox("Connect to Hardware")
        #self.controls_formLayout.addRow("Connect", self.connect_hardware_checkBox)
        #self.connect_hardware_checkBox.stateChanged.connect(self.enable_connection)

        
        self.control_widgets = OrderedDict()
        for lqname, lq in self.settings.as_dict().items():
            #: :type lq: LoggedQuantity
            if lq.choices is not None:
                widget = QtWidgets.QComboBox()
            elif lq.dtype in [int, float]:
                if lq.si:
                    widget = pg.SpinBox()
                else:
                    widget = QtWidgets.QDoubleSpinBox()
            elif lq.dtype in [bool]:
                widget = QtWidgets.QCheckBox()  
            elif lq.dtype in [str]:
                widget = QtWidgets.QLineEdit()
            lq.connect_bidir_to_widget(widget)

            # Add to formlayout
            self.controls_formLayout.addRow(lqname, widget)
            self.control_widgets[lqname] = widget
        
        self.op_buttons = OrderedDict()
        for op_name, op_func in self.operations.items(): 
            op_button = QtWidgets.QPushButton(op_name)
            op_button.clicked.connect(op_func)
            self.controls_formLayout.addRow(op_name, op_button)
        
        self.read_from_hardware_button = QtWidgets.QPushButton("Read From Hardware")
        self.read_from_hardware_button.clicked.connect(self.read_from_hardware)
        self.controls_formLayout.addRow("Logged Quantities:", self.read_from_hardware_button)
        
        return self.controls_groupBox
    
    def add_widgets_to_tree(self, tree):
        #tree = self.app.ui.hardware_treeWidget
        #tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels(["Hardware", "Value"])

        self.tree_item = QtWidgets.QTreeWidgetItem(tree, [self.name, "o"])
        tree.insertTopLevelItem(0, self.tree_item)
        self.tree_item.setFirstColumnSpanned(False)
        self.tree_item.setForeground(1, QtGui.QColor('red'))
        
        # Add logged quantities to tree
        self.settings.add_widgets_to_subtree(self.tree_item)        
        
        # Add oepration buttons to tree        
        self.op_buttons = OrderedDict()
        for op_name, op_func in self.operations.items(): 
            op_button = QtWidgets.QPushButton(op_name)
            op_button.clicked.connect(op_func)
            self.op_buttons[op_name] = op_button
            #self.controls_formLayout.addRow(op_name, op_button)
            op_tree_item = QtWidgets.QTreeWidgetItem(self.tree_item, [op_name, ""])
            tree.setItemWidget(op_tree_item, 1, op_button)

        self.tree_read_from_hardware_button = QtWidgets.QPushButton("Read From\nHardware")
        self.tree_read_from_hardware_button.clicked.connect(self.read_from_hardware)
        #self.controls_formLayout.addRow("Logged Quantities:", self.read_from_hardware_button)
        self.read_from_hardware_button_tree_item = QtWidgets.QTreeWidgetItem(self.tree_item, ["Logged Quantities:", ""])
        self.tree_item.addChild(self.read_from_hardware_button_tree_item)
        tree.setItemWidget(self.read_from_hardware_button_tree_item, 1, self.tree_read_from_hardware_button)

    @QtCore.Slot()    
    def read_from_hardware(self):
        """
        Read all settings (:class:`LoggedQuantity`) connected to hardware states
        """
        for name, lq in self.settings.as_dict().items():
            if lq.has_hardware_read():
                if self.debug_mode.val: self.log.debug("read_from_hardware {}".format(name) )
                lq.read_from_hardware()
        
    
    def connect(self):
        """
        Opens a connection to hardware
        and connects :class:`LoggedQuantity` settings to related hardware 
        functions and parameters 
        """
        raise NotImplementedError()
        
        
    def disconnect(self):
        """
        Disconnects the hardware and severs hardware--:class:`LoggedQuantity` links
        """
        
        raise NotImplementedError()
    
    @QtCore.Slot(bool)
    def enable_connection(self, enable=True):
        if enable:
            self.connect_success = False
            self.connect()
            self.connect_success = True
            self.tree_item.setText(1,'O')
            self.tree_item.setForeground(1, QtGui.QColor('green'))
        else:
            self.connect_success = False
            self.tree_item.setText(1,'X')
            self.tree_item.setForeground(1, QtGui.QColor('red'))
            self.disconnect()
            
            
    @property
    def gui(self):
        warnings.warn("Hardware.gui is deprecated, use Hardware.app", DeprecationWarning)
        return self.app
    
    def web_ui(self):
        return "Hardware {}".format(self.name)
    
    
    def thread_lock_lq(self, lq):
        lq.old_lock = lq.lock
        lq.lock = self.lock
        
    def thread_lock_all_lq(self):
        for lq in self.settings.as_list():
            lq.old_lock = lq.lock
            lq.lock = self.lock