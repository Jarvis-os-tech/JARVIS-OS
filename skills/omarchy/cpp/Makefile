CXX      := g++
CXXFLAGS := -O3 -Wall -Wextra -std=c++17
BINDIR   := ../bin
TARGET   := $(BINDIR)/omarchy_ctrl

.PHONY: all clean

all: $(TARGET)

$(BINDIR):
	mkdir -p $(BINDIR)

$(TARGET): omarchy_ctrl.cpp | $(BINDIR)
	$(CXX) $(CXXFLAGS) -o $@ $<
	@mkdir -p ../native/bin
	@cp -f $@ ../native/bin/omarchy_ctrl
	@echo "✅ omarchy_ctrl built and copied to skills/native/bin/omarchy_ctrl"

clean:
	rm -f $(TARGET)
