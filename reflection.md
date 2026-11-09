# Practice 10 - course reflection

## 1. Which features or idioms were most useful?

For me, semantic checking was one of the most useful parts of this course. I learned that a compiler can find errors before running a program.
For example, in tests/err/extern_bool_param.txt the compiler does not allow a bool parameter in an external function. 
This helped me understand why checking types is important. I also liked working with LLVM IR because I could see how our own programming language was changed into lower-level instructions.

## 2. Which features were not covered properly?

I think it would be useful to have more examples of how to find and fix errors in a compiler. During the practices sometimes I did not understand where the problem was.
It could be in the parser semantic checking or code generation. I think it would be easier if the teacher showed how to find an error step by step starting with 
a test that does not work and explaining how to fix it.

## 3. At least three surprising examples from languages and compilers

The first thing that surprised me was how our programming language could be changed into LLVM IR. Before this course I did not really understand how loops, conditions and functions work 
at a lower level. When I saw the generated .ll files I started to understand this process better. The second thing was that a program can generate correct LLVM IR but still have problems when 
creating an executable file. In Practice 10 we used llc-18 and clang. I learned that generating code and linking are different steps and an error can happen even after the LLVM IR was created. 
The third thing was that our language could use functions written in C. For example, in tests/ffi/geometry.txt we used extern fn to call isqrt() from geometry.c. I was surprised that we could 
connect two different programming languages like this

## 4. Which concepts or approaches are still unclear?

I still find it difficult to understand where some compiler errors come from. For example, when the compiler creates an LLVM IR file but the program does not work after that I do not always know 
what to check first. I am not sure if the problem is in the generated code, external functions or linking. Now I understand the main steps better but I still need more practice with finding and 
fixing these problems.

## 5. Other ideas and suggestions

I really liked this course because we did not only study theory but also worked on our own compiler. My main suggestion is to have more practical examples of debugging. For example, you 
could show a test that fails and then explain step by step how to find the problem and fix it. I also think it would be helpful to show more examples of using lli and clang. This would help to 
understand the difference between them and solve problems on our own.
Thank you for everything! I will miss your courses!
