; ARM64 Hello World Example
; Exit with status code 42

; .global _start

_start:
    mov x0, #42          ; Exit code
    mov x16, #1          ; syscall: exit
    svc #0x80            ; System call

; Fibonacci example
fibonacci:
    mov x0, #0           ; fib(0) = 0
    mov x1, #1           ; fib(1) = 1
    mov x2, #10          ; count
    
fib_loop:
    add x3, x0, x1       ; x3 = x0 + x1
    mov x0, x1           ; shift values
    mov x1, x3
    subs x2, x2, #1      ; decrement counter
    b.ne fib_loop        ; loop if not zero
    
    ret

; Memory operations
memory_test:
    adrp x0, data        ; Get page of data
    add x0, x0, :lo12:data
    ldr x1, [x0]         ; Load from memory
    str x1, [sp, #-16]!  ; Store to stack
    ldp x2, x3, [sp], #16  ; Load pair and pop
    ret

data:
    .quad 0x1234567890ABCDEF
