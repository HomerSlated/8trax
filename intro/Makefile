NASM      := nasm
NASMFLAGS := -f elf64
LD        := ld
LDFLAGS   := -dynamic-linker /lib64/ld-linux-x86-64.so.2 \
             -lX11 -lGL -lGLX -lz -lasound -lpthread -lc -lm
SSTRIP    := sstrip

.PHONY: all clean size

all: about

# Rasterize credit text: GLSL constants + compressed SDF atlas for the asm
text_blob.inc: tools/mktext.py
	python3 tools/mktext.py text_data.frag $@
text_data.frag: text_blob.inc ;

# Splice text constants into the shader at the //@TEXT_DATA@ marker
shader_full.frag: shader.frag text_data.frag
	awk '/@TEXT_DATA@/{while((getline l < "text_data.frag")>0) print l; next}1' shader.frag > $@

# Compress the GLSL shader into an asm include
shader_blob.inc: shader_full.frag tools/mkblob.py
	python3 tools/mkblob.py $< $@

about.o: about.asm shader_blob.inc text_blob.inc
	$(NASM) $(NASMFLAGS) -o $@ $<

about: about.o
	$(LD) $(LDFLAGS) -o $@ $<
	$(SSTRIP) $@

# Report raw ELF size and gzip-9 compressed size (the "4K" figure)
size: about
	@printf "raw:  %d bytes\n" $$(wc -c < about)
	@printf "gzip: %d bytes\n" $$(gzip -9 -c about | wc -c)

clean:
	rm -f about.o about shader_blob.inc shader_full.frag text_data.frag text_blob.inc
